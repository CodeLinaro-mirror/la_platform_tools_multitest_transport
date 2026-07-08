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

"""Unit tests for sql_models."""
import uuid

from absl.testing import absltest
from absl.testing import parameterized
import sqlalchemy as sa


from multitest_transport.models import sql_models
from multitest_transport.util import xts_result


class SqlModelsTest(parameterized.TestCase):

  def setUp(self):
    super(SqlModelsTest, self).setUp()
    sql_models.db.uri = 'sqlite:///:memory:'
    # Enable SQLite foreign key support
    def _SetSqlitePragma(dbapi_connection, _):
      cursor = dbapi_connection.cursor()
      cursor.execute('PRAGMA foreign_keys=ON')
      cursor.close()
    sa.event.listen(sql_models.db.engine, 'connect', _SetSqlitePragma)
    # Create tables
    sql_models.db.CreateTables()
    # Track executed statements
    self.statements = []
    sa.event.listen(
        sql_models.db.engine, 'before_cursor_execute',
        lambda *args: self.statements.append(args[2]))

  def tearDown(self):
    sql_models.db.DropTables()
    super(SqlModelsTest, self).tearDown()

  def testEntities(self):
    """Tests that entities can be inserted and queried."""
    with sql_models.db.Session() as session:
      # Insert a module and a nested test case
      module_id = str(uuid.uuid4())
      session.add(sql_models.TestModuleResult(
          id=module_id,
          test_run_id='test_run_id',
          attempt_id='attempt_id',
          name='module',
          complete=True,
          duration_ms=123,
          test_cases=[
              sql_models.TestCaseResult(
                  name='test_case',
                  status=xts_result.TestStatus.PASS,
              ),
          ],
          passed_tests=1,
          failed_tests=0,
          total_tests=1,
      ))

    with sql_models.db.Session() as session:
      # One module and test case inserted
      self.assertEqual(session.query(sql_models.TestModuleResult).count(), 1)
      self.assertEqual(session.query(sql_models.TestCaseResult).count(), 1)
      # Can fetch module by ID
      module = session.query(sql_models.TestModuleResult).get(module_id)
      self.assertIsNotNone(module)
      self.assertEqual(module.name, 'module')
      self.assertLen(module.test_cases, 1)
      # Can fetch test cases by relation
      test_cases = session.query(
          sql_models.TestCaseResult).with_parent(module).all()
      self.assertEqual(test_cases, module.test_cases)
      self.assertEqual(test_cases[0].module, module)
      self.assertEqual(test_cases[0].name, 'test_case')

  def testTruncate(self):
    """Tests that strings can be truncated."""
    self.assertIsNone(sql_models._Truncate(None, 10))
    self.assertEqual('hello world', sql_models._Truncate('hello world', 11))
    self.assertEqual('hello w...', sql_models._Truncate('hello world', 10))

  def testTruncateBytes(self):
    """Tests that strings can be truncated based on byte length."""
    self.assertIsNone(sql_models._TruncateBytes(None, 10))
    self.assertEqual(
        'hello world', sql_models._TruncateBytes('hello world', 11)
    )
    self.assertEqual('hello w...', sql_models._TruncateBytes('hello world', 10))
    # '\U0001F600' is 4 bytes in UTF-8
    self.assertEqual(
        '\U0001F600\U0001F600...',
        sql_models._TruncateBytes('\U0001F600\U0001F600\U0001F600', 11),
    )  # 8 bytes + 3 bytes '...' = 11 bytes.
    self.assertEqual(
        '\U0001F600...',
        sql_models._TruncateBytes('\U0001F600\U0001F600\U0001F600', 10),
    )  # 4 bytes + 3 bytes '...' = 7 bytes.

  @parameterized.parameters((100, 3), (2, 5))
  def testInsertTestResults(self, batch_size, num_statements):
    """Tests that *TS test results can be inserted efficiently."""
    sql_models.InsertTestResults('test_run_id', 'attempt_id', [
        xts_result.Module(
            name='module_1',
            complete=True,
            duration_ms=123,
            test_cases=[
                xts_result.TestCase(
                    name='test_1', status=xts_result.TestStatus.PASS),
                xts_result.TestCase(
                    name='test_2', status=xts_result.TestStatus.PASS),
            ],
        ),
        xts_result.Module(
            name='module_2',
            complete=False,
            duration_ms=456,
            test_cases=[
                xts_result.TestCase(
                    name='fail', status=xts_result.TestStatus.FAIL),
                xts_result.TestCase(
                    name='ignored', status=xts_result.TestStatus.IGNORED),
                xts_result.TestCase(
                    name='assumption',
                    status=xts_result.TestStatus.ASSUMPTION_FAILURE),
            ],
        )
    ], batch_size=batch_size)

    with sql_models.db.Session() as session:
      # 1 initial existence check and 2-3 statements per batch (insert and
      # optional update for modules and insert for test cases)
      self.assertLen(self.statements, num_statements)
      # All modules (and non-PASS test cases) inserted
      self.assertEqual(session.query(sql_models.TestModuleResult).count(), 2)
      self.assertEqual(session.query(sql_models.TestCaseResult).count(), 3)
      # Modules are associated with test cases and track pass/fail counts
      modules = session.query(sql_models.TestModuleResult).order_by(
          sql_models.TestModuleResult.name).all()
      self.assertEmpty(modules[0].test_cases)
      self.assertEqual(modules[0].passed_tests, 2)
      self.assertEqual(modules[0].failed_tests, 0)
      self.assertLen(modules[1].test_cases, 3)
      self.assertEqual(modules[1].passed_tests, 0)
      self.assertEqual(modules[1].failed_tests, 1)

  def testInsertTestResults_alreadyInserted(self):
    """Tests that *TS test results insertion is skipped if results found."""
    module = xts_result.Module(
        name='module_1', complete=True, duration_ms=123, test_cases=[])
    sql_models.InsertTestResults('test_run_id', 'attempt_id', [module])
    sql_models.InsertTestResults('test_run_id', 'attempt_id', [module])
    # Re-inserting the module has no effect (only 1 inserted).
    with sql_models.db.Session() as session:
      self.assertEqual(session.query(sql_models.TestModuleResult).count(), 1)

  def testGetTestModuleResults(self):
    attempt_ids = ['attempt_id_%s' % i for i in range(3)]
    with sql_models.db.Session() as session:
      for attempt_id in attempt_ids:
        session.add(
            sql_models.TestModuleResult(
                id=str(uuid.uuid4()),
                test_run_id='test_run_id',
                attempt_id=attempt_id,
                name=attempt_id,
                complete=True,
                duration_ms=123,
                passed_tests=1,
                failed_tests=0,
                total_tests=1))

    modules = sql_models.GetTestModuleResults(attempt_ids[:2])

    self.assertLen(modules, 2)
    self.assertCountEqual(
        ['attempt_id_0', 'attempt_id_1'], [m.name for m in modules])

if __name__ == '__main__':
  absltest.main()
