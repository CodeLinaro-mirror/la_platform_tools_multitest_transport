/**
 * Copyright 2024 Google LLC
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

import {DebugElement} from '@angular/core';
import {ComponentFixture, inject, TestBed} from '@angular/core/testing';
import {MatDialog} from '@angular/material/dialog';
import {NoopAnimationsModule} from '@angular/platform-browser/animations';
import {provideRouter} from '@angular/router';
import {of as observableOf} from 'rxjs';

import {APP_DATA} from '../services/app_data';
import * as mttModels from '../services/mtt_models';
import {MttObjectMap, MttObjectMapService, newMttObjectMap} from '../services/mtt_object_map';
import {TestRunConfigEditor} from '../test_runs/test_run_config_editor';
import {getTextContent} from '../testing/jasmine_util';

import {BuildsModule} from './builds_module';
import {TestRequirements} from './test_requirements';

describe('TestRequirements', () => {
  const REQUIRED_REPORTS = [
    {
      id: 'id1',
      type: mttModels.ReportType.CTS,
      test_plans: ['cts', 'cts-system']
    },
    {
      id: 'id2',
      type: mttModels.ReportType.GTS,
      test_plans: ['gts-interactive'],
    },
    {
      id: 'id3',
      type: mttModels.ReportType.VTS,
    },
  ];
  const TEST_MAP: {[id: string]: mttModels.Test} = {
    'test_id_1': {id: 'android.cts.9_0', name: 'name1'},
    'test_id_2': {id: 'android.cts.11_0', name: 'name2'},
    'test_id_3': {id: 'android.gts.11_0.android11_14', name: 'name3'},
    'test_id_4': {id: 'android.gts.11_1.android11_14', name: 'name4'},
  };

  let mttObjectMapService: jasmine.SpyObj<MttObjectMapService>;
  let mttObjectMap: MttObjectMap;
  let testRequirements: TestRequirements;
  let testRequirementsFixture: ComponentFixture<TestRequirements>;
  let el: DebugElement;

  beforeEach(() => {
    mttObjectMapService =
        jasmine.createSpyObj('mttObjectMapService', ['getMttObjectMap']);
    mttObjectMap = newMttObjectMap();
    mttObjectMapService.getMttObjectMap.and.returnValue(
        observableOf(mttObjectMap));

    TestBed.configureTestingModule({
      imports: [
        BuildsModule,
        NoopAnimationsModule,
      ],
      providers: [
        provideRouter([]),
        {provide: APP_DATA, useValue: {}},
        {provide: MttObjectMapService, useValue: mttObjectMapService},
      ],
    });

    testRequirementsFixture = TestBed.createComponent(TestRequirements);
    testRequirementsFixture.detectChanges();
    el = testRequirementsFixture.debugElement;
    testRequirements = testRequirementsFixture.componentInstance;
  });

  it('gets initialized', () => {
    expect(testRequirements).toBeTruthy();
  });

  it('should display test requirements correctly', () => {
    testRequirements.dataSource = REQUIRED_REPORTS;
    testRequirementsFixture.detectChanges();
    const textContent = getTextContent(el);
    for (const requiredReport of REQUIRED_REPORTS) {
      expect(textContent).toContain(requiredReport.type);
    }
  });

  it('should reset testRequirementDataMap correctly', () => {
    testRequirements.mttObjectMap.testMap = TEST_MAP;
    testRequirements.resetTestRequirementDataMap(REQUIRED_REPORTS);
    expect(testRequirements.testRequirementDataMap).toEqual({
      'id1':
          {selectedTestPlan: 'cts-system', defaultTest: TEST_MAP['test_id_2']},
      'id2': {
        selectedTestPlan: 'gts-interactive',
        defaultTest: TEST_MAP['test_id_4']
      },
      'id3': {selectedTestPlan: undefined, defaultTest: undefined},
    });
  });

  it('should get default test for a required report correctly', () => {
    testRequirements.mttObjectMap.testMap = TEST_MAP;
    expect(testRequirements.getDefaultTest(REQUIRED_REPORTS[0]))
        .toEqual(TEST_MAP['test_id_2']);
    expect(testRequirements.getDefaultTest(REQUIRED_REPORTS[1]))
        .toEqual(TEST_MAP['test_id_4']);
    expect(testRequirements.getDefaultTest(REQUIRED_REPORTS[2]))
        .toEqual(undefined);
  });

  it('should compare suite version of tests correctly', () => {
    expect(testRequirements.greaterThan(TEST_MAP['test_id_1'], undefined))
        .toEqual(true);
    expect(testRequirements.greaterThan(
               TEST_MAP['test_id_1'], TEST_MAP['test_id_2']))
        .toEqual(false);
    expect(testRequirements.greaterThan(
               TEST_MAP['test_id_3'], TEST_MAP['test_id_4']))
        .toEqual(false);
  });

  it('should disable the run button correctly', () => {
    testRequirements.mttObjectMap.testMap = TEST_MAP;
    testRequirements.resetTestRequirementDataMap(REQUIRED_REPORTS);
    expect(testRequirements.runButtonDisabled(REQUIRED_REPORTS[0]))
        .toEqual(false);
    expect(testRequirements.runButtonDisabled(REQUIRED_REPORTS[1]))
        .toEqual(false);
    expect(testRequirements.runButtonDisabled(REQUIRED_REPORTS[2]))
        .toEqual(true);
  });

  it('should open test run config editor with correct initial data',
     inject([MatDialog], (dialog: MatDialog) => {
       spyOn(dialog, 'open').and.callThrough();
       const defaultTest = TEST_MAP['test_id_1'];
       testRequirements.testRequirementDataMap = {
         'id1': {defaultTest, selectedTestPlan: 'cts-system'},
       };

       testRequirements.openTestRunConfigEditor(REQUIRED_REPORTS[0]);
       expect(dialog.open).toHaveBeenCalledTimes(1);

       const dialogParams = {
         panelClass: 'test-run-config-editor-dialog',
         data: {
           editMode: false,
           testRunConfig:
               mttModels.initTestRunConfig(defaultTest, 'cts-system'),
           testPlanToOverride: 'cts-system',
         },
       };
       expect(dialog.open)
           .toHaveBeenCalledWith(TestRunConfigEditor, dialogParams);
     }));
});
