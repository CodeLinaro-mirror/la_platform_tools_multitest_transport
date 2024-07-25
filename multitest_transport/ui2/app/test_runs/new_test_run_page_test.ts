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

import {LiveAnnouncer} from '@angular/cdk/a11y';
import {Component, DebugElement} from '@angular/core';
import {ComponentFixture, TestBed} from '@angular/core/testing';
import {MatChipInput} from '@angular/material/chips';
import {NoopAnimationsModule} from '@angular/platform-browser/animations';
import {provideRouter} from '@angular/router';
import {of as observableOf} from 'rxjs';

import {APP_DATA} from '../services/app_data';
import {FileService} from '../services/file_service';
import {MttClient, NetdataClient} from '../services/mtt_client';
import {Test, TestRun} from '../services/mtt_models';
import {MttObjectMap, MttObjectMapService, newMttObjectMap} from '../services/mtt_object_map';
import {TfcClient} from '../services/tfc_client';
import {getEl} from '../testing/jasmine_util';
import {newMockDeviceAction, newMockNetdataAlarmList, newMockNodeConfig, newMockTest, newMockTestRun} from '../testing/mtt_mocks';

import {NewTestRunPage} from './new_test_run_page';
import {TestRunsModule} from './test_runs_module';

@Component({
  selector: 'device-list',
  template: '',
  jit: true,
})
class DeviceListStubComponent {
}

describe('NewTestRunPage', () => {
  let newTestRunPage: NewTestRunPage;
  let newTestRunPageFixture: ComponentFixture<NewTestRunPage>;
  let liveAnnouncer: jasmine.SpyObj<LiveAnnouncer>;
  let mttClient: jasmine.SpyObj<MttClient>;
  let mttObjectMapService: jasmine.SpyObj<MttObjectMapService>;
  let netdataClient: jasmine.SpyObj<NetdataClient>;
  let tfcClient: jasmine.SpyObj<TfcClient>;

  let el: DebugElement;
  let test: Test;
  let testRun: TestRun;

  beforeEach(() => {
    test = newMockTest();
    testRun = newMockTestRun(test);

    liveAnnouncer =
        jasmine.createSpyObj('liveAnnouncer', ['announce', 'clear']);

    netdataClient = jasmine.createSpyObj(['getAlarms']);
    netdataClient.getAlarms.and.returnValue(observableOf({alarms: []}));

    mttClient = {
      ...jasmine.createSpyObj(['createNewTestRunRequest', 'getNodeConfig']),
      netdata: netdataClient,
    };
    mttClient.getNodeConfig.and.returnValue(observableOf(newMockNodeConfig()));

    mttObjectMapService = jasmine.createSpyObj(['getMttObjectMap']);
    mttObjectMapService.getMttObjectMap.and.returnValue(
        observableOf(newMttObjectMap()));

    tfcClient = jasmine.createSpyObj(['getFilterHintList', 'queryDeviceInfos']);
    tfcClient.getFilterHintList.and.returnValue(observableOf());
    tfcClient.queryDeviceInfos.and.returnValue(observableOf());

    TestBed.configureTestingModule({
      declarations: [DeviceListStubComponent],
      imports: [NoopAnimationsModule, TestRunsModule],
      providers: [
        provideRouter([]),
        {provide: APP_DATA, useValue: {hostname: 'hostname'}},
        {provide: LiveAnnouncer, useValue: liveAnnouncer},
        {provide: FileService, useValue: {}},
        {provide: MttClient, useValue: mttClient},
        {provide: MttObjectMapService, useValue: mttObjectMapService},
        {provide: TfcClient, useValue: tfcClient},
      ],
    });
    newTestRunPageFixture = TestBed.createComponent(NewTestRunPage);
    newTestRunPageFixture.detectChanges();
    el = newTestRunPageFixture.debugElement;
    newTestRunPage = newTestRunPageFixture.componentInstance;
  });

  function reload(objectMap: MttObjectMap) {
    mttObjectMapService.getMttObjectMap.and.returnValue(
        observableOf(newMttObjectMap()));
    newTestRunPage.loadData();
    newTestRunPageFixture.detectChanges();
  }

  it('initializes a component', () => {
    expect(newTestRunPage).toBeTruthy();
  });

  it('displays and announces a loading mask', () => {
    expect(liveAnnouncer.announce).toHaveBeenCalledWith('Loading', 'polite');
    expect(liveAnnouncer.announce)
        .toHaveBeenCalledWith('Test run loaded', 'assertive');
  });

  it('loads previous test run data', () => {
    newTestRunPage.loadPrevTestRun(testRun);
    expect(newTestRunPage.testRunConfig.test_id).toBe(test.id!);
  });

  it('can update the selected device action ids', () => {
    const objectMap = newMttObjectMap();
    const deviceAction = newMockDeviceAction('action.id');
    objectMap.deviceActionMap = {'action.id': deviceAction};
    reload(objectMap);

    expect(newTestRunPage.testRunConfig.before_device_action_ids!.length)
        .toEqual(0);
    newTestRunPage.selectedDeviceActions = [deviceAction];
    newTestRunPage.updateConfigDeviceActionIds();
    expect(newTestRunPage.testRunConfig.before_device_action_ids!).toEqual([
      'action.id'
    ]);
  });

  it('adds labels', () => {
    newTestRunPage.labels = [];
    const fakeInput = document.createElement('input');
    newTestRunPage.addLabel({
      chipInput: {inputElement: fakeInput} as MatChipInput,
      value: ' label1  '
    });
    expect(newTestRunPage.labels).toEqual(['label1']);
    newTestRunPage.addLabel({
      chipInput: {inputElement: fakeInput} as MatChipInput,
      value: 'label2'
    });
    expect(newTestRunPage.labels).toEqual(['label1', 'label2']);

    // Should not add duplicate label
    newTestRunPage.addLabel({
      chipInput: {inputElement: fakeInput} as MatChipInput,
      value: ' label1  '
    });
    expect(newTestRunPage.labels).toEqual(['label1', 'label2']);
  });

  it('removes labels', () => {
    newTestRunPage.labels = ['label1', 'label2', 'label3'];
    newTestRunPage.removeLabel('label2');
    expect(newTestRunPage.labels).toEqual(['label1', 'label3']);
    newTestRunPage.removeLabel('label3');
    expect(newTestRunPage.labels).toEqual(['label1']);
    newTestRunPage.removeLabel('label4');
    expect(newTestRunPage.labels).toEqual(['label1']);
    newTestRunPage.removeLabel('label1');
    expect(newTestRunPage.labels).toEqual([]);
    newTestRunPage.removeLabel('label1');
    expect(newTestRunPage.labels).toEqual([]);
  });

  it('displays warning message when there is an alarm on 1 host', () => {
    netdataClient.getAlarms.and.returnValue(
        observableOf(newMockNetdataAlarmList(
            'hostname', 1, 'disk_space._data.disk_space_usage', '80%')));

    getEl(el, '#start-test-run-button').click();

    expect(tfcClient.queryDeviceInfos).not.toHaveBeenCalled();
    expect(netdataClient.getAlarms)
        .toHaveBeenCalledWith(
            ['disk_space._data.disk_space_usage'], 'hostname');
    expect(newTestRunPage.warningMessage)
        .toEqual('Low disk space warning on hostname (80% used)');
  });

  it('displays warning message when there are alarms on hosts', () => {
    newTestRunPage.testRunConfig.device_specs = ['device_serial:123456'];
    tfcClient.queryDeviceInfos.and.returnValue(
        // TODO: Wait until b/208710526 is fixed, then remove this autogenerated
        // error suppression.
        //  @ts-ignore(go/unfork-jasmine-typings): Argument of type
        //  'Observable<{ deviceInfos: { hostname: string; }[]; }>' is not
        //  assignable to parameter of type
        //  'Observable<LabDeviceInfosResponse>'.
        observableOf({deviceInfos: [{hostname: 'hostname2'}]}));
    netdataClient.getAlarms
        .withArgs(['disk_space._data.disk_space_usage'], 'hostname')
        .and.returnValue(observableOf(newMockNetdataAlarmList(
            'hostname', 1, 'disk_space._data.disk_space_usage', '80%')));
    netdataClient.getAlarms
        .withArgs(['disk_space._data.disk_space_usage'], 'hostname2')
        .and.returnValue(observableOf(newMockNetdataAlarmList(
            'hostname2', 2, 'disk_space._data.disk_space_usage', '85%')));

    getEl(el, '#start-test-run-button').click();

    expect(tfcClient.queryDeviceInfos)
        .toHaveBeenCalledWith(
            {deviceSerial: ['123456'], includeOfflineDevices: false}, 1);
    expect(netdataClient.getAlarms).toHaveBeenCalledTimes(2);
    expect(newTestRunPage.warningMessage)
        .toEqual(
            'Low disk space warning on hostname (80% used)' +
            ' and 1 other host(s)');
  });

  it('does not create new test run request when there are disk space alarms',
     () => {
       netdataClient.getAlarms.and.returnValue(
           observableOf(newMockNetdataAlarmList(
               'hostname', 1, 'disk_space._data.disk_space_usage', '80%')));

       getEl(el, '#start-test-run-button').click();

       expect(mttClient.createNewTestRunRequest).not.toHaveBeenCalled();
     });

  it('creates new test run request when ignoring warnings', () => {
    netdataClient.getAlarms.and.returnValue(
        observableOf(newMockNetdataAlarmList(
            'hostname', 1, 'disk_space._data.disk_space_usage', '80%')));

    getEl(el, '#start-test-run-button').click();
    expect(mttClient.createNewTestRunRequest).not.toHaveBeenCalled();

    // Ignore warnings and start test run
    getEl(el, '#start-test-run-button').click();
    expect(mttClient.createNewTestRunRequest).toHaveBeenCalled();
  });

  it('does not display warning message when there is no alarm', () => {
    newTestRunPage.startTestRun();

    expect(newTestRunPage.warningMessage).toEqual('');
    expect(mttClient.createNewTestRunRequest).toHaveBeenCalled();
  });

  it('does not display warning message when netdata alarm requests fail',
     () => {
       netdataClient.getAlarms.and.throwError('Error');

       newTestRunPage.startTestRun();

       expect(newTestRunPage.warningMessage).toEqual('');
     });

  describe('back button', () => {
    it('should display correct aria-label and tooltip', () => {
      const backButton = getEl(el, '#back-button');
      expect(backButton).toBeTruthy();
      expect(backButton.getAttribute('aria-label'))
          .toBe('Return to test suites page');
      expect(backButton.getAttribute('mattooltip'))
          .toBe('Return to test suites page');
    });
  });
});
