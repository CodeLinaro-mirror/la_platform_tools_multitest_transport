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

"""Utilites for mtt.

Utilities in this module help general code execution.
"""

import threading


class Singleton(type):
  """Singleton metaclass.

  Usage:
  class Foo(..., metaclass=util.Singleton):
    pass
  """

  _instances = {}
  _instances_lock = threading.Lock()

  def __call__(cls, *args, **kwargs):
    """It is thread safe to create the singleton instance."""
    if cls not in cls._instances:
      with cls._instances_lock:
        if cls not in cls._instances:
          cls._instances[cls] = super().__call__(*args, **kwargs)
    return cls._instances[cls]
