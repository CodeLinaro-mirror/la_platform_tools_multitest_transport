/**
 * Copyright 2020 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

import * as testUtil from '../testing/mtt_mocks';
import * as mttModels from './mtt_models';

describe('MttModels', () => {
  describe('initTestRunConfig', () => {
    it('creates a default empty config', () => {
      const config = mttModels.initTestRunConfig();
      expect(config.test_id).toEqual('');
      expect(config.run_count).toEqual(mttModels.DEFAULT_RUN_COUNT);
      expect(config.command).toEqual('');
      expect(config.retry_command).toEqual('');
      expect(config.shard_count).toEqual(mttModels.DEFAULT_SHARD_COUNT);
      expect(config.max_retry_on_test_failures)
          .toEqual(mttModels.DEFAULT_MAX_RETRY_ON_TEST_FAILURES);
      expect(config.queue_timeout_seconds)
          .toEqual(mttModels.DEFAULT_QUEUE_TIMEOUT_SECONDS);
      expect(config.output_idle_timeout_seconds)
          .toEqual(mttModels.DEFAULT_OUTPUT_IDLE_TIMEOUT_SECONDS);
    });

    it('creates a config with a test\'s default values', () => {
      const test = testUtil.newMockTest();
      const config = mttModels.initTestRunConfig(test);
      const parameters = test.default_test_run_parameters;
      expect(config.test_id).toEqual(test.id);
      expect(config.command).toEqual(test.command);
      expect(config.retry_command).toEqual(test.retry_command_line);
      expect(config.max_retry_on_test_failures)
          .toEqual(parameters.max_retry_on_test_failures);
      expect(config.output_idle_timeout_seconds)
          .toEqual(parameters.output_idle_timeout_seconds);
    });
  });

  describe('updateSelectedDeviceActions', () => {
    const deviceSpecs = [
      'device_serial:host:local-virtual-device-1 device_type:LOCAL_VIRTUAL',
      'device_serial:AB'
    ];
    const deviceActions: mttModels.DeviceAction[] = [
      testUtil.newMockDeviceAction('id1', 'No pattern'),
      testUtil.newMockDeviceAction('id2', 'Match'),
      testUtil.newMockDeviceAction('id3', 'Not match'),
    ];
    deviceActions[1].device_spec =
        '\\bdevice_serial:\\S+:local-virtual-device-\\d+\\b';
    deviceActions[2].device_spec = '\\bdevice_serial:A\\b';

    it('adds the device actions with device_spec', () => {
      const expectedSelections = [deviceActions[1]];

      const updatedSelections =
          mttModels.updateSelectedDeviceActions([], deviceActions, deviceSpecs);

      expect(updatedSelections).toEqual(expectedSelections);
    });

    it('removes the device actions with device_spec', () => {
      const expectedSelections = [deviceActions[0], deviceActions[1]];

      const updatedSelections = mttModels.updateSelectedDeviceActions(
          deviceActions, deviceActions, deviceSpecs);

      expect(updatedSelections).toEqual(expectedSelections);
    });
  });

  describe('getNamespaceFromId', () => {
    it('returns the correct namespace', () => {
      const id = 'ns1.test/catalog::abc.123';
      const namespace = mttModels.getNamespaceFromId(id);
      expect(namespace).toEqual('ns1.test/catalog');
    });

    it('handles an id without a namespace', () => {
      const id = 'abc:123/cde.456';
      const namespace = mttModels.getNamespaceFromId(id);
      expect(namespace).toEqual('');
    });
  });
});
