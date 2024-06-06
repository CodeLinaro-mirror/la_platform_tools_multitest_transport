/**
 * Copyright 2021 Google LLC
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

import {HttpClientTestingModule} from '@angular/common/http/testing';
import {DebugElement} from '@angular/core';
import {ComponentFixture, TestBed} from '@angular/core/testing';
import {NoopAnimationsModule} from '@angular/platform-browser/animations';
import {of as observableOf} from 'rxjs';

import {APP_DATA} from '../services/app_data';
import {DeviceAction, Test, TestRunConfig} from '../services/mtt_models';
import {MttObjectMap, MttObjectMapService, newMttObjectMap} from '../services/mtt_object_map';
import {getEl, getTextContent} from '../testing/jasmine_util';
import {newMockDeviceAction, newMockTest, newMockTestRunConfig} from '../testing/mtt_mocks';

import {TestRunConfigSummary} from './test_run_config_summary';
import {TestRunsModule} from './test_runs_module';

describe('TestRunConfigSummary', () => {
  let testRunConfig: TestRunConfig;
  let test: Test;
  let deviceAction1: DeviceAction;
  let deviceAction2: DeviceAction;
  let mttData: MttObjectMap;
  let mttObjectMapService: jasmine.SpyObj<MttObjectMapService>;

  let testRunConfigSummary: TestRunConfigSummary;
  let testRunConfigSummaryFixture: ComponentFixture<TestRunConfigSummary>;
  let el: DebugElement;

  beforeEach(() => {
    mttData = newMttObjectMap();

    test = newMockTest('test1');
    mttData.testMap = {[test.id!]: test};

    deviceAction1 = newMockDeviceAction('action.abc', 'Action ABC');
    deviceAction2 = newMockDeviceAction('action.def', 'Action DEF');
    mttData.deviceActionMap = {
      [deviceAction1.id]: deviceAction1,
    };

    testRunConfig = newMockTestRunConfig(test.id!);
    testRunConfig.before_device_action_ids =
        [deviceAction1.id, deviceAction2.id];
    testRunConfig.device_specs = [
      'device_serial:device_a', 'device_serial:device_b',
      'device_serial:device_c'
    ];

    mttObjectMapService = jasmine.createSpyObj(['getMttObjectMap']);
    mttObjectMapService.getMttObjectMap.and.returnValue(observableOf(mttData));
    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule, NoopAnimationsModule, TestRunsModule],
      providers: [
        {provide: APP_DATA, useValue: {}},
        {provide: MttObjectMapService, useValue: mttObjectMapService},
      ],
    });

    testRunConfigSummaryFixture = TestBed.createComponent(TestRunConfigSummary);
    el = testRunConfigSummaryFixture.debugElement;
    testRunConfigSummary = testRunConfigSummaryFixture.componentInstance;
    testRunConfigSummary.config = testRunConfig;
    testRunConfigSummary.title = 'Config Title 3';
    testRunConfigSummaryFixture.detectChanges();
  });

  it('should get initialized correctly', () => {
    expect(testRunConfigSummary).toBeTruthy();
  });

  it('displays full details summary', () => {
    const textContent = getTextContent(el);
    expect(textContent).toContain('Config Title 3');
    expect(textContent).toContain(test.name);
    expect(textContent).toContain(testRunConfig.command);

    expect(textContent).toContain('device_a');
    expect(textContent).toContain('device_b');
    expect(textContent).toContain('device_c');

    expect(textContent).toContain('Action ABC');
    expect(textContent).toContain('action.def');
  });

  it('displays minimized summary', () => {
    getEl(el, '.view-details-button').click();
    testRunConfigSummaryFixture.detectChanges();

    const textContent = getTextContent(el);
    expect(textContent).toContain('Config Title 3');
    expect(textContent).toContain(test.name);
    expect(textContent).toContain('3 (device_serial:device_a, ...)');    // Run targets
    expect(textContent).toContain('2 (Action ABC, ...)');  // Device actions

    expect(textContent).not.toContain('Command:');
    expect(textContent).not.toContain('device_b');
  });

  describe('delete button', () => {
    it('should display correct aria-label and tooltip', () => {
      const deleteButton = getEl(el, '.delete-button');
      expect(deleteButton).toBeTruthy();
      expect(deleteButton.getAttribute('aria-label')).toBe('Delete');
      expect(deleteButton.getAttribute('matTooltip')).toBe('Delete');
    });
  });
});
