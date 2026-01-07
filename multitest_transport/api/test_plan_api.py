# Copyright 2019 Google LLC
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

"""A module to provide test plan APIs."""
# Non-standard docstrings are used to generate the API documentation.

import croniter
import endpoints
from protorpc import message_types
from protorpc import messages
from protorpc import remote

from tradefed_cluster.util import ndb_shim as ndb


from multitest_transport.api import base
from multitest_transport.models import build
from multitest_transport.models import messages as mtt_messages
from multitest_transport.models import ndb_models
from multitest_transport.test_scheduler import test_kicker
from multitest_transport.test_scheduler import test_plan_kicker
from multitest_transport.test_scheduler import test_scheduler


def _IsValidCronExpression(cron_exp):
  """Check validity of a given cron expression.

  Args:
    cron_exp: a cron expression.
  Returns:
    True if valid. Otherwise False.
  """
  try:
    croniter.croniter(cron_exp)
  except ValueError:
    return False
  return True


def _ValidateTestPlan(test_plan):
  """Check validity of a given test plan.

  Args:
    test_plan: a ndb_models.TestPlan object.
  """
  if test_plan.cron_exp and not _IsValidCronExpression(test_plan.cron_exp):
    raise endpoints.BadRequestException(
        ('Invalid cron expression (%s). Cron expression should be ordered as '
         'minute, hour, day of month, month, day of week.')
        % test_plan.cron_exp)

  for sequence in test_plan.test_run_sequences:
    for config in sequence.test_run_configs:
      if not config.test_key.get():
        raise endpoints.BadRequestException(
            'Test %s does not exist' % config.test_key.id())

      config_device_actions = ndb.get_multi(
          config.before_device_action_keys)
      if not all(config_device_actions):
        raise endpoints.BadRequestException(
            'Cannot find some device actions: %s -> %s' % (
                config.before_device_action_keys, config_device_actions))
      test_kicker.ValidateDeviceActions(config_device_actions)

      for obj in config.test_resource_objs:
        build_locator = build.BuildLocator.ParseUrl(obj.url)
        if build_locator and not mtt_messages.ConvertToKey(
            ndb_models.BuildChannelConfig,
            build_locator.build_channel_id).get():
          raise endpoints.BadRequestException(
              'Build channel %s does not exist' %
              build_locator.build_channel_id)


@base.MTT_API.api_class(resource_name='test_plan', path='test_plans')
class TestPlanApi(remote.Service):
  """A handler for Test Plan API."""

  @base.ApiMethod(
      endpoints.ResourceContainer(message_types.VoidMessage),
      mtt_messages.TestPlanList, path='/test_plans', http_method='GET',
      name='list')
  def List(self, request):
    """Lists test plans."""
    test_plans = list(ndb_models.TestPlan.query()
                      .order(ndb_models.TestPlan.name))
    test_plan_msgs = mtt_messages.ConvertList(
        test_plans, mtt_messages.TestPlan)
    return mtt_messages.TestPlanList(test_plans=test_plan_msgs)

  @base.ApiMethod(
      endpoints.ResourceContainer(mtt_messages.TestPlan),
      mtt_messages.TestPlan, path='/test_plans', http_method='POST',
      name='create')
  def Create(self, request):
    """Creates a test plan.

    Body:
      Test plan data
    """
    test_plan = mtt_messages.Convert(
        request, ndb_models.TestPlan, from_cls=mtt_messages.TestPlan)
    _ValidateTestPlan(test_plan)
    test_plan.key = None
    test_plan.put()
    test_scheduler.ScheduleTestPlanCronJob(test_plan.key.id())
    return mtt_messages.Convert(test_plan, mtt_messages.TestPlan)

  @base.ApiMethod(
      endpoints.ResourceContainer(
          message_types.VoidMessage,
          test_plan_id=messages.StringField(1, required=True)),
      mtt_messages.TestPlan, path='{test_plan_id}', http_method='GET',
      name='get')
  def Get(self, request):
    """Fetches a test plan.

    Parameters:
      test_plan_id: Test plan ID, or zero for an empty test plan
    """
    if request.test_plan_id == '0':
      # For ID 0, return an empty test plan object to use as a template in UI.
      test_plan = ndb_models.TestPlan(id=0, name='')
    else:
      test_plan = mtt_messages.ConvertToKey(
          ndb_models.TestPlan, request.test_plan_id).get()
    if not test_plan:
      raise endpoints.NotFoundException(
          'No test plan with ID %s' % request.test_plan_id)
    return mtt_messages.Convert(test_plan, mtt_messages.TestPlan)

  @base.ApiMethod(
      endpoints.ResourceContainer(
          mtt_messages.TestPlan,
          test_plan_id=messages.StringField(1, required=True)),
      mtt_messages.TestPlan, path='{test_plan_id}', http_method='PUT',
      name='update')
  def Update(self, request):
    """Updates a test plan.

    Body:
      Test plan data
    Parameters:
      test_plan_id: Test plan ID
    """
    test_plan_key = mtt_messages.ConvertToKey(
        ndb_models.TestPlan, request.test_plan_id)
    if not test_plan_key.get():
      raise endpoints.NotFoundException()
    test_plan = mtt_messages.Convert(
        request, ndb_models.TestPlan, from_cls=mtt_messages.TestPlan)
    _ValidateTestPlan(test_plan)
    test_plan.key = test_plan_key
    test_plan.put()
    test_scheduler.ScheduleTestPlanCronJob(test_plan.key.id())
    return mtt_messages.Convert(test_plan, mtt_messages.TestPlan)

  @base.ApiMethod(
      mtt_messages.TestPlanList,
      mtt_messages.TestPlanList,
      path='batch_update', http_method='POST',
      name='batch_update')
  def BatchUpdate(self, request):
    """Updates multiple test plans.

    Body:
      Test plan list data
    """
    updated_plans = []
    for plan_msg in request.test_plans:
      if not plan_msg.id:
        raise endpoints.BadRequestException('Test plan ID is required')
      test_plan_key = mtt_messages.ConvertToKey(
          ndb_models.TestPlan, plan_msg.id
      )
      if not test_plan_key.get():
        raise endpoints.NotFoundException(
            'Test plan %s not found' % plan_msg.id
        )

      test_plan = mtt_messages.Convert(
          plan_msg, ndb_models.TestPlan, from_cls=mtt_messages.TestPlan
      )
      _ValidateTestPlan(test_plan)
      test_plan.key = test_plan_key
      test_plan.put()
      test_scheduler.ScheduleTestPlanCronJob(test_plan.key.id())
      updated_plans.append(test_plan)

    return mtt_messages.TestPlanList(
        test_plans=mtt_messages.ConvertList(
            updated_plans, mtt_messages.TestPlan
        )
    )

  @base.ApiMethod(
      endpoints.ResourceContainer(
          message_types.VoidMessage,
          test_plan_id=messages.StringField(1, required=True),
      ),
      message_types.VoidMessage,
      path='{test_plan_id}',
      http_method='DELETE',
      name='delete',
  )
  def Delete(self, request):
    """Deletes a test plan.

    Parameters:
      test_plan_id: Test plan ID
    """
    test_plan_key = mtt_messages.ConvertToKey(
        ndb_models.TestPlan, request.test_plan_id)
    test_plan_key.delete()
    return message_types.VoidMessage()

  @base.ApiMethod(
      endpoints.ResourceContainer(
          message_types.VoidMessage,
          test_plan_id=messages.StringField(1, required=True)),
      message_types.VoidMessage, path='{test_plan_id}/run', http_method='POST',
      name='run')
  def Run(self, request):
    """Runs a test plan immediately.

    Parameters:
      test_plan_id: Test plan ID
    """
    test_plan = mtt_messages.ConvertToKey(
        ndb_models.TestPlan, request.test_plan_id).get()
    if not test_plan:
      raise endpoints.NotFoundException('Test plan %s does not exist'
                                        % request.test_plan_id)
    if not test_plan.test_run_sequences:
      raise endpoints.BadRequestException(
          'No test run configs with ID %s' % request.test_plan_id)
    test_plan_kicker.KickTestPlan(test_plan.key.id())
    # TODO: returns a test plan job object.
    return message_types.VoidMessage()
