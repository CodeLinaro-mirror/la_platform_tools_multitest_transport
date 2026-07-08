# Copyright 2020 Google LLC
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

"""Extensions to the OpenAPI spec generator."""
from endpoints.openapi_generator import OpenApiGenerator


def ApiMethodDescriptor(summary=None, description=None, deprecated=None):
  """Decorator which adds metadata about an endpoints method."""
  def _Decorator(method):
    if summary:
      method.method_info.summary = summary
    if description:
      method.method_info.description = description
    if deprecated is not None:
      method.method_info.deprecated = deprecated
    return method
  return _Decorator


class DescriptiveOpenApiGenerator(OpenApiGenerator):
  """OpenAPI spec generator which injects additional metadata.

  See Also
    https://cloud.google.com/endpoints/docs/frameworks/python/endpoints_tool
    https://swagger.io/specification/#operation-object
  """

  def _OpenApiGenerator__method_descriptor(self, service, method_info,
                                           operation_id, protorpc_method_info,
                                           security_definitions):
    descriptor = super(DescriptiveOpenApiGenerator,  # pyrefly: ignore[missing-attribute]
                       self)._OpenApiGenerator__method_descriptor(
                           service, method_info, operation_id,
                           protorpc_method_info, security_definitions)
    descriptor['tags'] = [service.api_info.resource_name]
    descriptor['summary'] = getattr(method_info, 'summary', None)
    descriptor['description'] = getattr(method_info, 'description', None)
    descriptor['deprecated'] = getattr(method_info, 'deprecated', False)
    return descriptor
