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
import {ComponentFixture, inject, TestBed} from '@angular/core/testing';
import {MatDialog} from '@angular/material/dialog';
import {NoopAnimationsModule} from '@angular/platform-browser/animations';
import {provideRouter} from '@angular/router';
import {of as observableOf} from 'rxjs';

import {APP_DATA} from '../services/app_data';
import {initTestRunConfig, Test, TestRunConfig, TestRunConfigList} from '../services/mtt_models';
import {MttObjectMap, MttObjectMapService, newMttObjectMap} from '../services/mtt_object_map';
import {getEl, getEls, getTextContent} from '../testing/jasmine_util';
import {newMockTest, newMockTestRunConfig} from '../testing/mtt_mocks';

import {TestRunConfigEditor, TestRunConfigEditorData} from './test_run_config_editor';
import {TestRunSequenceList} from './test_run_sequence_list';
import {TestRunsModule} from './test_runs_module';

describe('TestRunSequenceList', () => {
  let testRunSequences: TestRunConfigList[];
  let test1: Test;
  let test2: Test;
  let config1: TestRunConfig;
  let config2: TestRunConfig;
  let testMap: {[id: string]: Test};
  let mttData: MttObjectMap;
  let mttObjectMapService: jasmine.SpyObj<MttObjectMapService>;

  let testRunSequenceList: TestRunSequenceList;
  let testRunSequenceListFixture: ComponentFixture<TestRunSequenceList>;
  let el: DebugElement;

  beforeEach(() => {
    test1 = newMockTest('test.1', 'test1');
    test2 = newMockTest('xts.2.0', 'xTS 2.0');
    testMap = {[test1.id!]: test1, [test2.id!]: test2};
    config1 = newMockTestRunConfig(test1.id!);
    config2 = newMockTestRunConfig(test2.id!);
    testRunSequences =
        [{test_run_configs: [config1]}, {test_run_configs: [config2]}];
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

    testRunSequenceListFixture = TestBed.createComponent(TestRunSequenceList);
    el = testRunSequenceListFixture.debugElement;
    testRunSequenceList = testRunSequenceListFixture.componentInstance;
    testRunSequenceList.sequenceList = testRunSequences;
    testRunSequenceListFixture.detectChanges();
  });

  it('should get initialized correctly', () => {
    expect(testRunSequenceList).toBeTruthy();

    const textContent = getTextContent(el);
    expect(textContent).toContain(test1.name);
    expect(textContent).toContain(test2.name);
  });

  it('should displays correct number of items', () => {
    const items = getEls(el, '.mat-mdc-card');
    expect(items).toBeTruthy();
    expect(items.length).toBe(testRunSequenceList.sequenceList.length);
  });

  it('can delete items', () => {
    testRunSequenceList.deleteSequence(0);
    testRunSequenceListFixture.detectChanges();

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
       testRunSequenceList.addSequence();
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
       testRunSequenceList.sequenceList = [];
       testRunSequenceListFixture.detectChanges();
       spyOn(dialog, 'open').and.callThrough();
       testRunSequenceList.addSequence();
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
       testRunSequenceList.sequenceList = [];
       testRunSequenceList.configTemplate = config1;
       testRunSequenceListFixture.detectChanges();
       spyOn(dialog, 'open').and.callThrough();
       testRunSequenceList.addSequence();
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

  it('can delete sequence', () => {
    spyOn(testRunSequenceList.sequenceListChange, 'emit');
    testRunSequenceList.deleteSequence(0);
    expect(testRunSequenceList.sequenceList.length).toBe(1);
    expect(testRunSequenceList.sequenceListChange.emit).toHaveBeenCalledWith(
        testRunSequenceList.sequenceList);
  });

  it('can update config list', () => {
    spyOn(testRunSequenceList.sequenceListChange, 'emit');
    const newConfigList = [config1, config2];
    testRunSequenceList.updateConfigList(0, newConfigList);
    expect(testRunSequenceList.sequenceList[0].test_run_configs).toBe(newConfigList);
    expect(testRunSequenceList.sequenceListChange.emit).toHaveBeenCalledWith(
        testRunSequenceList.sequenceList);
  });
});
