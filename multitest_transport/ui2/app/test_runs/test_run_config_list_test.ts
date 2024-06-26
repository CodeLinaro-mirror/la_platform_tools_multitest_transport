/**
 * Copyright 2019 Google LLC
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
import {ComponentFixture, inject, TestBed} from '@angular/core/testing';
import {MatDialog} from '@angular/material/dialog';
import {NoopAnimationsModule} from '@angular/platform-browser/animations';
import {provideRouter} from '@angular/router';
import {of as observableOf} from 'rxjs';

import {APP_DATA} from '../services/app_data';
import {initTestRunConfig, Test, TestRunConfig} from '../services/mtt_models';
import {MttObjectMap, MttObjectMapService, newMttObjectMap} from '../services/mtt_object_map';
import {getEl, getEls, getTextContent} from '../testing/jasmine_util';
import {newMockTest, newMockTestRunConfig} from '../testing/mtt_mocks';

import {TestRunConfigEditor, TestRunConfigEditorData} from './test_run_config_editor';
import {TestRunConfigList} from './test_run_config_list';
import {TestRunsModule} from './test_runs_module';

describe('TestRunConfigList', () => {
  let testRunConfigs: TestRunConfig[];
  let test1: Test;
  let test2: Test;
  let config1: TestRunConfig;
  let config2: TestRunConfig;
  let testMap: {[id: string]: Test};
  let mttData: MttObjectMap;
  let mttObjectMapService: jasmine.SpyObj<MttObjectMapService>;

  let testRunConfigList: TestRunConfigList;
  let testRunConfigListFixture: ComponentFixture<TestRunConfigList>;
  let el: DebugElement;

  beforeEach(() => {
    test1 = newMockTest('test.1', 'test1');
    test2 = newMockTest('xts.2.0', 'xTS 2.0');
    testMap = {[test1.id!]: test1, [test2.id!]: test2};
    config1 = newMockTestRunConfig(test1.id!);
    config2 = newMockTestRunConfig(test2.id!);
    testRunConfigs = [config1, config2];
    mttData = newMttObjectMap();
    mttData.testMap = testMap;
    mttObjectMapService = jasmine.createSpyObj(['getMttObjectMap']);
    mttObjectMapService.getMttObjectMap.and.returnValue(observableOf(mttData));

    TestBed.configureTestingModule({
      imports: [NoopAnimationsModule, TestRunsModule],
      providers: [
        provideHttpClientTesting(),
        provideRouter([]),
        {provide: APP_DATA, useValue: {}},
        {provide: MttObjectMapService, useValue: mttObjectMapService},
      ],
    });

    testRunConfigListFixture = TestBed.createComponent(TestRunConfigList);
    el = testRunConfigListFixture.debugElement;
    testRunConfigList = testRunConfigListFixture.componentInstance;
    testRunConfigList.data = testRunConfigs;
    testRunConfigListFixture.detectChanges();
  });

  it('should get initialized correctly', () => {
    expect(testRunConfigList).toBeTruthy();

    const textContent = getTextContent(el);
    expect(textContent).toContain(test1.name);
    expect(textContent).toContain(test2.name);
  });

  it('should displays correct number of items', () => {
    const items = getEls(el, '.mat-mdc-card');
    expect(items).toBeTruthy();
    expect(items.length).toBe(testRunConfigList.data.length);
  });

  it('can delete items', () => {
    testRunConfigList.deleteConfig(0);
    testRunConfigListFixture.detectChanges();

    const textContent = getTextContent(el);
    expect(textContent).not.toContain(test1.name);
    expect(textContent).toContain(test2.name);

    const items = getEls(el, '.mat-mdc-card');
    expect(items).toBeTruthy();
    expect(items.length).toBe(1);
  });

  it('should open test run config editor with the last config',
     inject([MatDialog], (dialog: MatDialog) => {
       spyOn(dialog, 'open').and.callThrough();
       testRunConfigList.addConfig();
       expect(dialog.open).toHaveBeenCalledTimes(1);

       const testRunConfigEditorData: TestRunConfigEditorData = {
         editMode: false,
         testRunConfig: config2,
       };
       expect(dialog.open).toHaveBeenCalledWith(TestRunConfigEditor, {
         panelClass: 'test-run-config-editor-dialog',
         data: testRunConfigEditorData,
       });
     }));

  it('should open test run config editor with a new config',
     inject([MatDialog], (dialog: MatDialog) => {
       testRunConfigList.data = [];
       testRunConfigListFixture.detectChanges();
       spyOn(dialog, 'open').and.callThrough();
       testRunConfigList.addConfig();
       expect(dialog.open).toHaveBeenCalledTimes(1);

       const testRunConfigEditorData: TestRunConfigEditorData = {
         editMode: false,
         testRunConfig: initTestRunConfig(test1),
       };
       expect(dialog.open).toHaveBeenCalledWith(TestRunConfigEditor, {
         panelClass: 'test-run-config-editor-dialog',
         data: testRunConfigEditorData,
       });
     }));

  it('should open test run config editor with a config template',
     inject([MatDialog], (dialog: MatDialog) => {
       testRunConfigList.data = [];
       testRunConfigList.configTemplate = config1;
       testRunConfigListFixture.detectChanges();
       spyOn(dialog, 'open').and.callThrough();
       testRunConfigList.addConfig();
       expect(dialog.open).toHaveBeenCalledTimes(1);

       const testRunConfigEditorData: TestRunConfigEditorData = {
         editMode: false,
         testRunConfig: config1,
       };
       expect(dialog.open).toHaveBeenCalledWith(TestRunConfigEditor, {
         panelClass: 'test-run-config-editor-dialog',
         data: testRunConfigEditorData,
       });
     }));

  describe('add button', () => {
    it('should display correct aria-label and tooltip', () => {
      const addButton = getEl(el, '.add-button');
      expect(addButton).toBeTruthy();
      expect(addButton.getAttribute('aria-label'))
          .toBe('Add test run configuration');
    });
  });
});
