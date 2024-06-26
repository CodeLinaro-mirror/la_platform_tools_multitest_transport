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

import {provideHttpClientTesting} from '@angular/common/http/testing';
import {DebugElement} from '@angular/core';
import {ComponentFixture, TestBed} from '@angular/core/testing';
import {NoopAnimationsModule} from '@angular/platform-browser/animations';
import {of as observableOf} from 'rxjs';

import {APP_DATA} from '../services/app_data';
import {DeviceAction, Test, TestRunConfig} from '../services/mtt_models';
import {MttObjectMap, MttObjectMapService, newMttObjectMap} from '../services/mtt_object_map';
import {getEl, getTextContent} from '../testing/jasmine_util';
import {newMockDeviceAction, newMockTest, newMockTestRunConfig} from '../testing/mtt_mocks';

import {TestRunSequenceEditor} from './test_run_sequence_editor';
import {TestRunsModule} from './test_runs_module';

describe('TestRunSequenceEditor', () => {
  let testRunConfig: TestRunConfig;
  let testRunConfig2: TestRunConfig;
  let test: Test;
  let test2: Test;
  let deviceAction1: DeviceAction;
  let deviceAction2: DeviceAction;
  let mttData: MttObjectMap;
  let mttObjectMapService: jasmine.SpyObj<MttObjectMapService>;

  let testRunSequenceEditor: TestRunSequenceEditor;
  let testRunSequenceEditorFixture: ComponentFixture<TestRunSequenceEditor>;
  let el: DebugElement;

  beforeEach(() => {
    mttData = newMttObjectMap();

    test = newMockTest('test1', 'Test One');
    test2 = newMockTest('test2', 'Second test');
    mttData.testMap = {
      [test.id!]: test,
      [test2.id!]: test2,
    };

    deviceAction1 = newMockDeviceAction('action.abc', 'Action ABC');
    deviceAction2 = newMockDeviceAction('action.def', 'Action DEF');
    mttData.deviceActionMap = {
      [deviceAction1.id]: deviceAction1,
    };

    testRunConfig = newMockTestRunConfig(test.id!);
    testRunConfig2 = newMockTestRunConfig(test2.id!);
    testRunConfig.before_device_action_ids =
        [deviceAction1.id, deviceAction2.id];
    testRunConfig.device_specs = [
      'device_serial:device_a',
      'device_serial:device_b',
      'device_serial:device_c',
    ];

    mttObjectMapService = jasmine.createSpyObj(['getMttObjectMap']);
    mttObjectMapService.getMttObjectMap.and.returnValue(observableOf(mttData));
    TestBed.configureTestingModule({
      imports: [NoopAnimationsModule, TestRunsModule],
      providers: [
        provideHttpClientTesting(),
        {provide: APP_DATA, useValue: {}},
        {provide: MttObjectMapService, useValue: mttObjectMapService},
      ],
    });

    testRunSequenceEditorFixture =
        TestBed.createComponent(TestRunSequenceEditor);
    el = testRunSequenceEditorFixture.debugElement;
    testRunSequenceEditor = testRunSequenceEditorFixture.componentInstance;
    testRunSequenceEditor.configList = [testRunConfig, testRunConfig2];
    testRunSequenceEditor.title = 'Config Title 3';
    testRunSequenceEditorFixture.detectChanges();
  });

  it('should get initialized correctly', () => {
    expect(testRunSequenceEditor).toBeTruthy();
  });

  it('displays the primary config', () => {
    const textContent = getTextContent(el);
    expect(textContent).toContain('Config Title 3');
    expect(textContent).toContain(test.name);
    expect(textContent).toContain(testRunConfig.command);

    expect(textContent).toContain('device_a');
    expect(textContent).toContain('device_b');
    expect(textContent).toContain('device_c');

    expect(textContent).toContain('Action ABC');
    expect(textContent).toContain('action.def');

    expect(textContent).toContain('View 1 rerun config(s)');
  });

  it('displays rerun config details', () => {
    getEl(el, '.show-rerun-configs-button').click();
    testRunSequenceEditorFixture.detectChanges();

    const textContent = getTextContent(el);
    expect(textContent).toContain('Rerun Config 1');
    expect(textContent).toContain(test2.name);
    expect(textContent).toContain('Hide 1 rerun config(s)');
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
