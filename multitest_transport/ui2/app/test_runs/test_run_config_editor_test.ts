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

import {provideHttpClientTesting} from '@angular/common/http/testing';
import {DebugElement} from '@angular/core';
import {ComponentFixture, TestBed} from '@angular/core/testing';
import {MAT_DIALOG_DATA, MatDialogRef} from '@angular/material/dialog';
import {By} from '@angular/platform-browser';
import {NoopAnimationsModule} from '@angular/platform-browser/animations';
import {provideRouter} from '@angular/router';
import {of as observableOf} from 'rxjs';

import {DeviceList} from '../devices/device_list';
import {APP_DATA} from '../services/app_data';
import {MttClient} from '../services/mtt_client';
import {LabDeviceInfo} from '../services/mtt_lab_models';
import {MttObjectMapService, newMttObjectMap} from '../services/mtt_object_map';
import {Notifier} from '../services/notifier';
import {TfcClient} from '../services/tfc_client';
import {newMockLabDeviceInfo} from '../testing/mtt_lab_mocks';
import {newMockDeviceAction, newMockTest, newMockTestRunConfig} from '../testing/mtt_mocks';

import {TestRunConfigEditor} from './test_run_config_editor';
import {TestRunsModule} from './test_runs_module';

describe('TestRunConfigEditor', () => {
  let testRunConfigEditor: TestRunConfigEditor;
  let testRunConfigEditorFixture: ComponentFixture<TestRunConfigEditor>;
  let deviceList: DeviceList;
  let el: DebugElement;
  let mttClient: jasmine.SpyObj<MttClient>;
  let mttObjectMapService: jasmine.SpyObj<MttObjectMapService>;
  let device1: LabDeviceInfo;
  let device2: LabDeviceInfo;
  let tfcClient: jasmine.SpyObj<TfcClient>;
  let notifierSpy: jasmine.SpyObj<Notifier>;

  const test = newMockTest('test_id_1', 'test_name_1');
  const dialogRefSpy =
      jasmine.createSpyObj('MatDialogRef', ['close', 'backdropClick']);

  beforeEach(() => {
    device1 = newMockLabDeviceInfo('device1Id');
    device2 = newMockLabDeviceInfo('device2Id');

    mttClient = jasmine.createSpyObj('mttClient', ['getTest']);
    mttClient.getTest.and.returnValue(observableOf(test));
    mttObjectMapService = jasmine.createSpyObj(['getMttObjectMap']);
    mttObjectMapService.getMttObjectMap.and.returnValue(
        observableOf(newMttObjectMap()));
    dialogRefSpy.backdropClick.and.returnValue(observableOf({}));

    tfcClient = jasmine.createSpyObj('tfcClient', {
      batchGetDevicesLatestNotes: observableOf({}),
      getFilterHintList: observableOf({filter_hints: []}),
      queryDeviceInfos: observableOf({deviceInfos: [device1, device2]}),
    });

    notifierSpy = jasmine.createSpyObj('notifier', {
      confirm: observableOf(true),  // mock confirm click in dialog.
      showMessage: observableOf({}),
      showError: observableOf({}),
    });

    TestBed.configureTestingModule({
      imports: [NoopAnimationsModule, TestRunsModule],
      providers: [
        provideHttpClientTesting(),
        provideRouter([]),
        {provide: APP_DATA, useValue: {isAtsLabInstance: false}},
        {provide: MttClient, useValue: mttClient},
        {
          provide: MAT_DIALOG_DATA,
          useFactory: () => ({
            editMode: false,
            testRunConfig:
                newMockTestRunConfig(test.id, 'command', 'retry_command', '', 0)
          })
        },
        {provide: MatDialogRef, useValue: dialogRefSpy},
        {provide: MttObjectMapService, useValue: mttObjectMapService},
        {provide: Notifier, useValue: notifierSpy},
        {provide: TfcClient, useValue: tfcClient},
      ],
    });

    testRunConfigEditorFixture = TestBed.createComponent(TestRunConfigEditor);
    el = testRunConfigEditorFixture.debugElement;
    testRunConfigEditor = testRunConfigEditorFixture.componentInstance;
    testRunConfigEditorFixture.detectChanges();
    deviceList = el.query(By.directive(DeviceList)).componentInstance;
    deviceList.dataSource = [];
  });

  function reload(objectMap = newMttObjectMap()) {
    mttObjectMapService.getMttObjectMap.and.returnValue(
        observableOf(objectMap));
    testRunConfigEditor.load();
    testRunConfigEditorFixture.detectChanges();
  }

  it('initializes a component', () => {
    expect(testRunConfigEditor).toBeTruthy();
  });

  it('should return device specs correctly', () => {
    const testedDevices = [device1, device2];
    expect(testRunConfigEditor.data.testRunConfig.device_specs).toEqual([]);

    deviceList.updateSelectedDeviceSerials(
        testedDevices.map((device) => device.device_serial));
    expect(testRunConfigEditor.data.testRunConfig.device_specs)
        .toEqual(testedDevices.map(
            (device) => `device_serial:${device.device_serial}`));

    deviceList.updateSelectedDeviceSerials([]);
    expect(testRunConfigEditor.data.testRunConfig.device_specs).toEqual([]);
  });

  it('should create new test run config correctly on submit', () => {
    testRunConfigEditor.data.editMode = false;
    spyOn(testRunConfigEditor.configSubmitted, 'emit');
    testRunConfigEditor.submit();
    expect(testRunConfigEditor.configSubmitted.emit)
        // TODO: Wait until b/208710526 is fixed, then remove this autogenerated
        // error suppression.
        //  @ts-ignore(go/unfork-jasmine-typings): Argument of type
        //  'Partial<TestRunConfig>' is not assignable to parameter of type
        //  'Expected<TestRunConfig | undefined>'.
        .toHaveBeenCalledWith(testRunConfigEditor.data.testRunConfig);
    expect(dialogRefSpy.close).toHaveBeenCalled();
  });

  it('can update the selected device action ids', () => {
    const objectMap = newMttObjectMap();
    const deviceAction = newMockDeviceAction('action.id');
    objectMap.deviceActionMap = {'action.id': deviceAction};
    reload(objectMap);

    expect(
        testRunConfigEditor.data.testRunConfig.before_device_action_ids!.length)
        .toEqual(0);
    testRunConfigEditor.selectedDeviceActions = [deviceAction];
    testRunConfigEditor.updateConfigDeviceActionIds();
    expect(testRunConfigEditor.data.testRunConfig.before_device_action_ids!)
        .toEqual(['action.id']);
  });

  it('should update test run config correctly on submit', () => {
    testRunConfigEditor.data.editMode = true;
    const testedDevices =
        [newMockLabDeviceInfo('device1Id'), newMockLabDeviceInfo('device2Id')];
    deviceList.updateSelectedDeviceSerials(
        testedDevices.map((device) => device.device_serial));
    testRunConfigEditor.submit();
    expect(testRunConfigEditor.data.testRunConfig.device_specs)
        .toEqual(testedDevices.map(
            (device) => `device_serial:${device.device_serial}`));
    expect(dialogRefSpy.close).toHaveBeenCalled();
  });
});
