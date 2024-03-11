# Copyright 2021 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""SQL-based model classes (for the test results DB)."""
import logging
from typing import Iterable, List, Optional
import uuid

import sqlalchemy as sa


from multitest_transport.util import env
from multitest_transport.util import sql_util
from multitest_transport.util import xts_result

# Database connection recycle time
_CONNECTION_RECYCLE_SECONDS = 3600
# MySQL option to enable compressed tables
_COMPRESSED_ROW_FORMAT = {'mysql_row_format': 'compressed'}
# Maximum length of a text column
_TEXT_MAX_LENGTH = 65535
# Default number of test result rows to insert at a time
RESULTS_BATCH_SIZE = 100000
# Maximum length of a module/test name
_NAME_MAX_LENGTH = 255

# Database manager singleton
db = sql_util.Database(
    uri=env.SQL_DATABASE_URI,
    pool_pre_ping=True,
    pool_recycle=_CONNECTION_RECYCLE_SECONDS,
)


class TestModuleResult(db.Model):
  """Test module containing multiple test case results."""

  __tablename__ = 'test_module_result'
  __table_args__ = (_COMPRESSED_ROW_FORMAT,)

  id = sa.Column(sa.String(36), primary_key=True)
  test_run_id = sa.Column(sa.String(36), nullable=False, index=True)
  attempt_id = sa.Column(sa.String(36), nullable=False, index=True)
  name = sa.Column(sa.String(_NAME_MAX_LENGTH), nullable=False)
  duration_ms = sa.Column(sa.Integer, nullable=False)
  complete = sa.Column(sa.Boolean, nullable=False)
  test_cases = sa.orm.relationship(
      'TestCaseResult',
      backref='module',
      lazy=True,
      cascade='all, delete-orphan',
      passive_deletes=True,
  )
  passed_tests = sa.Column(sa.Integer, nullable=False)
  failed_tests = sa.Column(sa.Integer, nullable=False)
  total_tests = sa.Column(sa.Integer, nullable=False)
  error_message = sa.Column(sa.Text)


class TestCaseResult(db.Model):
  """Test case with result and debugging information."""

  __tablename__ = 'test_case_result'
  __table_args__ = (_COMPRESSED_ROW_FORMAT,)

  id = sa.Column(sa.Integer, primary_key=True)
  module_id = sa.Column(
      sa.String(36),
      sa.ForeignKey('test_module_result.id', ondelete='CASCADE'),
      nullable=False,
  )
  name = sa.Column(sa.String(_NAME_MAX_LENGTH), nullable=False)
  status = sa.Column(sql_util.IntEnum(xts_result.TestStatus), nullable=False)
  error_message = sa.Column(sa.Text)
  stack_trace = sa.Column(sa.Text)


def _Truncate(value: Optional[str], max_length: int) -> Optional[str]:
  """Truncate a string if it exceeds the maximum length."""
  if value and len(value) > max_length:
    return value[: max_length - 3] + '...'
  return value


def InsertTestResults(
    test_run_id: str,
    attempt_id: str,
    test_results: Iterable[xts_result.Module],
    batch_size: int = RESULTS_BATCH_SIZE,
):
  """Efficiently inserts large test results into the database.

  Extracts raw test case data and executes batch inserts with pre-populated IDs.
  This is significantly (10x) faster than using the ORM and letting the database
  auto-generate IDs.

  Args:
    test_run_id: test run ID to associate modules with
    attempt_id: attempt ID to associate modules with
    test_results: xts_result.TestResults
    batch_size: number of test cases to insert at a time
  """
  with db.Session() as session:
    if session.query(TestModuleResult).filter_by(attempt_id=attempt_id).first():
      logging.warning('Found test results for %s; skipping insertion')
      return

  with db.Session() as session:
    test_case_data = []
    # Iterate over modules, convert to entities with pre-populated IDs
    for module in test_results:
      module_entity = TestModuleResult(
          id=str(uuid.uuid4()),
          test_run_id=test_run_id,
          attempt_id=attempt_id,
          name=_Truncate(module.name, _NAME_MAX_LENGTH),
          complete=module.complete,
          duration_ms=module.duration_ms,
          passed_tests=0,
          failed_tests=0,
          total_tests=0,
          error_message=_Truncate(module.error_message, _TEXT_MAX_LENGTH),
      )
      session.add(module_entity)

      # Iterate over test cases, convert to dicts, and set module ID
      for test_case in module.test_cases:
        # Track test case statistics
        module_entity.total_tests += 1
        if test_case.status == xts_result.TestStatus.PASS:
          module_entity.passed_tests += 1
          continue  # Skip storing passed test cases to preserve disk space
        elif test_case.status == xts_result.TestStatus.FAIL:
          module_entity.failed_tests += 1
        # Append raw data
        test_case_data.append(
            dict(
                module_id=module_entity.id,
                name=_Truncate(test_case.name, _NAME_MAX_LENGTH),
                status=test_case.status,
                error_message=_Truncate(
                    test_case.error_message, _TEXT_MAX_LENGTH
                ),
                stack_trace=_Truncate(test_case.stack_trace, _TEXT_MAX_LENGTH),
            )
        )
        # Bulk insert raw test case data in batches to reduce memory usage
        if len(test_case_data) >= batch_size:
          session.commit()  # Persist modules (ensure foreign keys are valid)
          session.bulk_insert_mappings(TestCaseResult, test_case_data)
          test_case_data = []

      # Ensure test case statistics will be updated if necessary
      session.add(module_entity)

    # Persist any remaining modules and test cases
    session.commit()
    session.bulk_insert_mappings(TestCaseResult, test_case_data)


def GetTestModuleResults(attempt_ids: List[str]) -> List[TestModuleResult]:
  """Queries test modules results for a given attempt IDs.

  Args:
    attempt_ids: attempt IDs.

  Returns:
    a list of test module results.
  """
  with db.Session() as session:
    query = session.query(TestModuleResult)
    query = query.filter(TestModuleResult.attempt_id.in_(attempt_ids))
    return query.all()
