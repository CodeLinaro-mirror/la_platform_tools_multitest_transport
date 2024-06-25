# Copyright 2024 Google LLC
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

"""Tests for util."""

from absl.testing import absltest
from multitest_transport.util import util


class Foo(metaclass=util.Singleton):
  pass


class Bar(metaclass=util.Singleton):
  pass


class UtilTest(absltest.TestCase):

  def test_class_singleton(self):
    self.assertIs(Foo(), Foo())
    self.assertIs(Bar(), Bar())
    self.assertIsNot(Foo(), Bar())


if __name__ == "__main__":
  absltest.main()
