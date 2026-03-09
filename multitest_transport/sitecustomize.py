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
"""sitecustomize for google3 imports."""

import sys

import google3  

from grpc._cython import cygrpc  

from google3.google.protobuf import field_mask_pb2
from google3.google.protobuf import timestamp_pb2
import google3.google.type


# Search installed packages first (necessary to use host-side grpc package).
sys.path.sort(key=lambda p: p.endswith('google3/third_party/py'))

# Protos used by android.ci.build.v4.
sys.modules['google.type'] = google3.google.type
sys.modules['google.protobuf.field_mask_pb2'] = field_mask_pb2
sys.modules['google.protobuf.timestamp_pb2'] = timestamp_pb2
