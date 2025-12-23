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

"""Utilities for parsing *TS results."""
from typing import BinaryIO, Iterator, List, Optional

import attr
from defusedxml.cElementTree import iterparse as defused_iterparse
from protorpc import messages


@attr.s(auto_attribs=True, frozen=True, slots=True)
class Summary(object):
  """Results summary."""
  TAG = 'Summary'
  passed: int
  failed: int
  modules_done: int
  modules_total: int

  @classmethod
  def FromElement(cls, element) -> 'Summary':
    """Parses a summary from an XML element."""
    return Summary(
        passed=int(element.attrib['pass']),
        failed=int(element.attrib['failed']),
        modules_done=int(element.attrib['modules_done']),
        modules_total=int(element.attrib['modules_total']))


class TestStatus(messages.Enum):
  """Test outcome."""
  UNKNOWN = 0
  PASS = 1
  FAIL = 2
  IGNORED = 3
  ASSUMPTION_FAILURE = 4


@attr.s(auto_attribs=True, frozen=True, slots=True)
class TestCase(object):
  """Test case results."""
  TAG = 'TestCase'
  name: str
  status: TestStatus
  error_message: Optional[str] = None
  stack_trace: Optional[str] = None

  @classmethod
  def FromElement(cls, element) -> List['TestCase']:
    """Parses a list of test cases from an XML element."""
    class_name = element.attrib['name']
    test_cases = []
    for e in element.iterfind('Test'):
      try:
        status = TestStatus.lookup_by_name(e.attrib['result'].upper())
      except KeyError:
        status = TestStatus.UNKNOWN
      error = e.find('Failure')
      test_case = TestCase(
          name='%s#%s' % (class_name, e.attrib['name']),
          status=status,
          error_message=error.attrib['message'] if error else None,
          stack_trace=error.findtext('StackTrace') if error else None)
      test_cases.append(test_case)
    return test_cases


@attr.s(auto_attribs=True, frozen=True, slots=True)
class Module(object):
  """Module results."""
  TAG = 'Module'
  name: str
  complete: bool
  duration_ms: int
  test_cases: List[TestCase]
  error_message: Optional[str] = None

  @classmethod
  def FromElement(cls, element) -> 'Module':
    """Parses a module from an XML element."""
    name = element.attrib['name']
    abi = element.attrib.get('abi')
    if abi:
      name = '%s %s' % (abi, name)

    error_message = None
    test_cases = []
    for e in element.iter():
      if e.tag == TestCase.TAG:
        test_cases.extend(TestCase.FromElement(e))
        e.clear()  # Release memory held by test case element
      elif e.tag == 'Reason':
        error_message = e.attrib['message']

    return Module(
        name=name,
        complete=element.attrib['done'] == 'true',
        duration_ms=int(element.attrib.get('runtime') or 0),
        test_cases=test_cases,
        error_message=error_message)


class TestResults(object):
  """Iteratively parses a *TS test result XML file and returns the contents."""

  def __init__(self, xml_stream: BinaryIO):
    """Initializes the XML iterator and parses the metadata."""
    self._iter = iter(defused_iterparse(xml_stream, events=('start', 'end')))
    self.summary = self._ParsePreamble()

  def __iter__(self) -> Iterator[Module]:
    """Iterates over module results."""
    return self._ParseModules()

  def _ParsePreamble(self) -> Optional[Summary]:
    """Parses elements prior to the first module."""
    summary = None
    # Parse elements until a 'Module' element is found
    for event, element in self._iter:
      if event != 'start':
        continue
      if element.tag == Summary.TAG:
        summary = Summary.FromElement(element)
      elif element.tag == Module.TAG:
        break
    return summary

  def _ParseModules(self) -> Iterator[Module]:
    """Iteratively parses module elements and their test results."""
    for event, element in self._iter:
      if event == 'end' and element.tag == Module.TAG:
        module = Module.FromElement(element)
        element.clear()  # Release memory held by module element
        yield module
