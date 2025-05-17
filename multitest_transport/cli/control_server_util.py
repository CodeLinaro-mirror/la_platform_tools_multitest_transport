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

"""Utils for control server interactions."""
import datetime
import logging
import apiclient.discovery
import apiclient.errors
import google_auth_httplib2
import httplib2

from multitest_transport.cli import google_auth_util

logger = logging.getLogger(__name__)

_API_VERSION = 'v1'
_DISCOVERY_URL = '{}/$discovery/rest?version={}'
_HOST_UPDATE_STATE_CHANGED_EVENT_TYPE = 'HOST_UPDATE_STATE_CHANGED'
_DEFAULT_HTTP_TIMEOUT_SECONDS = 60


def _CreateControlServerApiClient(
    control_server_url, service_account_json_key_path, api_key):
  """Create control server API client.

  Args:
    control_server_url: text, the control server url pointing to control
      service.
    service_account_json_key_path: text, the path to key file to generate
      credentials.
    api_key: text, the api key for API discovery.

  Returns:
    A Resource object with methods for interacting with the control service, or
    None if cannot create client.
  """
  if not (control_server_url and service_account_json_key_path and
          api_key):
    logger.debug(
        'No control service API client is created, '
        'because control_server_url<%s> '
        'or service_account_json_key_path<%s> '
        'or api_key<%s> is not found.',
        control_server_url,
        service_account_json_key_path,
        api_key)
    return

  creds = google_auth_util.CreateCredentialFromServiceAccount(
      service_account_json_key_path,
      scopes=[google_auth_util.ANDROID_TEST_API_SCOPE])
  control_server_api_client = None
  try:
    # We use _retrieve_discovery_doc and build_from_document because discovery
    # requires api key. If we use apiclient.discovery.build, the api key will
    # be used both for discovery and actual client request. And it will error
    # out due to the api key and service account are not from same project.
    # By separating the two steps, we use different auth for the two steps:
    # api key for discovery and service account for api call.
    api_doc = apiclient.discovery._retrieve_discovery_doc(  
        url=_DISCOVERY_URL.format(control_server_url, _API_VERSION),
        http=httplib2.Http(timeout=_DEFAULT_HTTP_TIMEOUT_SECONDS),
        serviceName='',  # unused, required positional argument
        version=_API_VERSION,  # unused, required positional argument
        cache_discovery=False,
        developerKey=api_key,
        static_discovery=False)
    http = google_auth_httplib2.AuthorizedHttp(
        creds, httplib2.Http(timeout=_DEFAULT_HTTP_TIMEOUT_SECONDS))
    control_server_api_client = apiclient.discovery.build_from_document(
        api_doc,
        http=http)
  except Exception:  
    logger.exception('Failed to create Control Server API client.')
  return control_server_api_client


class ControlServerClient(object):
  """Control server client."""

  def __init__(
      self, control_server_url, service_account_json_key_path,
      api_key):
    """ControlServerClient constructor.

    Args:
      control_server_url: url to control server.
      service_account_json_key_path: service account key to authenticate control
        server request.
      api_key: api key to create apiclient discovery client.
    """
    self._control_server_url = control_server_url
    self._service_account_json_key_path = service_account_json_key_path
    self._api_key = api_key

  def _CreateControlServerApiClient(self):
    """Create an instance of control server client."""
    return _CreateControlServerApiClient(
        self._control_server_url, self._service_account_json_key_path,
        self._api_key)

  def SubmitHostUpdateStateChangedEvent(
      self, hostname, host_update_state_name, display_message=None,
      target_image=None):
    """Submit a HOST_UPDATE_STATE_CHANGED event to control server API.

      This function only submit the host event when control server API is
      available.

    Args:
      hostname: host name.
      host_update_state_name: text, the name of host update state.
      display_message: optional text, the display message to further clarity a
        host update state.
      target_image: optional text, the target harness image which the host
        tries to update to.
    Raises:
      apiclient.errors.HttpError.
    """
    # The client needs to be created every time when submit the event, because
    # the credentials expires quickly, and the update process could take hours.
    control_server_api_client = self._CreateControlServerApiClient()
    if not control_server_api_client:
      logger.debug('No control server API client is created, '
                   'skip submitting host update events.')
      return

    
    now_sec = int(datetime.datetime.utcnow()
                  .replace(tzinfo=datetime.timezone.utc).timestamp())
    body = {
        'host_events': [
            {
                'time': now_sec,
                'event_type': _HOST_UPDATE_STATE_CHANGED_EVENT_TYPE,
                'host_update_state': host_update_state_name,
                'hostname': hostname,
                'host_update_state_display_message': display_message,
                'data': {
                    'host_update_target_image': target_image,
                },
            },
        ]
    }
    try:
      control_server_api_client.test().hostEvents().submit(body=body).execute()
      logger.info('Submitted HostEvent<%s> to control server.', body)
    except (apiclient.errors.HttpError, httplib2.HttpLib2Error):
      logger.exception('Error when submitting HostEvent to control server.')

  def GetHostMetadata(self, hostname):
    """Get host metadata.

    Args:
      hostname: host name.

    Returns:
      a python dict representing the HostMetadata.

    Raises:
      apiclient.errors.HttpError.
    """
    control_server_api_client = self._CreateControlServerApiClient()
    try:
      host_metadata = control_server_api_client.test(
          ).hosts().getMetadata(hostname=hostname).execute()
      return host_metadata
    except apiclient.errors.HttpError as err:
      logger.exception(
          'Error when looking up metadata for host: %s.', hostname)
      raise err

  def PatchTestHarnessImageToHostMetadata(self, hostname, test_harness_image):
    """Patch test_harness_image field to host metadata.

    Args:
      hostname: host name.
      test_harness_image: string, url to test harness image.

    Raises:
      apiclient.errors.HttpError.
    """
    control_server_api_client = self._CreateControlServerApiClient()
    try:
      body = {
          'test_harness_image': test_harness_image,
      }
      control_server_api_client.test().hosts().patchMetadata(
          hostname=hostname, body=body).execute()
    except apiclient.errors.HttpError as err:
      logger.exception(
          'Error when patching metadata for host: %s.', hostname)
      raise err
