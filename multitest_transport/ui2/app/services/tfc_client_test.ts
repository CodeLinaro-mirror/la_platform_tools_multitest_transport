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

import {HttpClient, HttpParams} from '@angular/common/http';
import {of as observableOf} from 'rxjs';

import * as mttLabModels from '../services/mtt_lab_models';
import * as mocks from '../testing/mtt_lab_mocks';
import {newMockDeviceInfo, newMockHostUpdateStateSummary} from '../testing/mtt_lab_mocks';
import {newMockCommand, newMockCommandAttempt, newMockInvocationStatus, newMockRequest} from '../testing/mtt_mocks';

import {AnalyticsContext} from './analytics_service';
import {ONLINE_DEVICE_STATES, TfcClient} from './tfc_client';
import * as tfcModels from './tfc_models';
import {DeviceInfosResponse} from './tfc_models';

describe('TfcClient', () => {
  let httpClientSpy: jasmine.SpyObj<HttpClient>;
  let tfcClient: TfcClient;
  const appData = mocks.newMockAppData();
  const serial = 'device1';
  const hostname = 'host01';
  const harnemssImage = 'repo/image:tag';
  const maxResults = 10;
  const pageToken = '';
  const backwards = false;

  describe('getDeviceInfos', () => {
    const DEVICES: DeviceInfosResponse = {device_infos: [newMockDeviceInfo()]};

    beforeEach(() => {
      httpClientSpy = jasmine.createSpyObj('HttpClient', ['get']);
      tfcClient = new TfcClient(appData, httpClientSpy);
      httpClientSpy.get.and.returnValue(observableOf(DEVICES));
    });

    it('calls API and parses response correctly', () => {
      const observable = tfcClient.getDeviceInfos();
      const params = new HttpParams().appendAll({
        'device_states': ONLINE_DEVICE_STATES,
        'count': 1000,
      });
      expect(httpClientSpy.get)
          .toHaveBeenCalledWith(`${tfcClient.tfcApiUrl}/devices`, {params});
      expect(httpClientSpy.get).toHaveBeenCalledTimes(1);

      observable.subscribe((response) => {
        expect(response).toEqual(DEVICES);
      });
    });
  });

  describe('getRequestInvocationStatus', () => {
    const invocationStatus = newMockInvocationStatus();

    beforeEach(() => {
      httpClientSpy = jasmine.createSpyObj('HttpClient', ['get']);
      tfcClient = new TfcClient(appData, httpClientSpy);
      httpClientSpy.get.and.returnValue(observableOf(invocationStatus));
    });

    it('calls API and parses response correctly', () => {
      const observable = tfcClient.getRequestInvocationStatus('requestid');
      expect(httpClientSpy.get)
          .toHaveBeenCalledWith(
              `${tfcClient.tfcApiUrl}/requests/requestid/invocation_status`);
      expect(httpClientSpy.get).toHaveBeenCalledTimes(1);

      observable.subscribe((response) => {
        expect(response).toEqual(invocationStatus);
      });
    });
  });

  describe('getRequest', () => {
    const attempt = newMockCommandAttempt();
    const command = newMockCommand();
    const request = newMockRequest([command], [attempt]);

    beforeEach(() => {
      httpClientSpy = jasmine.createSpyObj('HttpClient', ['get']);
      httpClientSpy.get.and.returnValue(observableOf(request));
    });

    it('calls API and parses response correctly', () => {
      const appData =
          mocks.newMockAppData(undefined, undefined, undefined, true, true);
      tfcClient = new TfcClient(appData, httpClientSpy);
      const observable = tfcClient.getRequest(request.id);
      observable.subscribe((response) => {
        expect(response).toEqual(request);
      });

      const params = new HttpParams().set('force', 'true');
      expect(httpClientSpy.get)
          .toHaveBeenCalledWith(
              `${tfcClient.apiUrl}/requests/${request.id}`, {params});
      expect(httpClientSpy.get).toHaveBeenCalledTimes(1);
    });

    it('calls API without force param when not isOmniLabBased', () => {
      const appData =
          mocks.newMockAppData(undefined, undefined, undefined, true, false);
      tfcClient = new TfcClient(appData, httpClientSpy);
      const observable = tfcClient.getRequest(request.id);
      observable.subscribe((response) => {
        expect(response).toEqual(request);
      });

      expect(httpClientSpy.get)
          .toHaveBeenCalledWith(
              `${tfcClient.tfcApiUrl}/requests/${request.id}`);
      expect(httpClientSpy.get).toHaveBeenCalledTimes(1);
    });
  });

  describe('getHostInfos', () => {
    const rawHostInfos = mocks.newMockHostInfosResponse();
    const hostInfos = mocks.newMockLabHostInfosResponse();
    let params: HttpParams;

    beforeEach(() => {
      httpClientSpy = jasmine.createSpyObj('HttpClient', ['get']);
      tfcClient = new TfcClient(appData, httpClientSpy);
      httpClientSpy.get.and.returnValue(observableOf(rawHostInfos));
      params = new HttpParams({
        fromObject: {
          'count': String(maxResults),
          'cursor': pageToken,
          'backwards': String(backwards),
        }
      });
    });

    it('calls API and parses response correctly', () => {
      const observable = tfcClient.getHostInfos(undefined);
      expect(httpClientSpy.get)
          .toHaveBeenCalledWith(`${tfcClient.tfcApiUrl}/hosts`, {params});
      expect(httpClientSpy.get).toHaveBeenCalledTimes(1);
      observable.subscribe((response) => {
        expect(response).toEqual(hostInfos);
      });
    });

    it('calls API with lab name "All" correctly', () => {
      const searchCriteria = {lab: mttLabModels.ALL_OPTIONS_VALUE};
      tfcClient.getHostInfos(searchCriteria);
      expect(httpClientSpy.get)
          .toHaveBeenCalledWith(`${tfcClient.tfcApiUrl}/hosts`, {params});
      expect(httpClientSpy.get).toHaveBeenCalledTimes(1);
    });

    it('calls API with lab name correctly', () => {
      const searchCriteria = {lab: 'lab-1'};
      tfcClient.getHostInfos(searchCriteria);
      params = params.append('lab_name', 'lab-1');
      expect(httpClientSpy.get)
          .toHaveBeenCalledWith(`${tfcClient.tfcApiUrl}/hosts`, {params});
      expect(httpClientSpy.get).toHaveBeenCalledTimes(1);
    });

    it('calls API with hostnames correctly', () => {
      const searchCriteria = {hostnames: ['host-1', 'host-2']};
      tfcClient.getHostInfos(searchCriteria);
      params =
          params.append('hostnames', 'host-1').append('hostnames', 'host-2');
      expect(httpClientSpy.get)
          .toHaveBeenCalledWith(`${tfcClient.tfcApiUrl}/hosts`, {params});
      expect(httpClientSpy.get).toHaveBeenCalledTimes(1);
    });

    it('calls API with hostGroups correctly', () => {
      const searchCriteria = {hostGroups: ['group-1', 'group-2']};
      tfcClient.getHostInfos(searchCriteria);
      params = params.append('host_groups', 'group-1')
                   .append('host_groups', 'group-2');
      expect(httpClientSpy.get)
          .toHaveBeenCalledWith(`${tfcClient.tfcApiUrl}/hosts`, {params});
      expect(httpClientSpy.get).toHaveBeenCalledTimes(1);
    });

    it('calls API with testHarness correctly', () => {
      const searchCriteria = {testHarness: ['tf']};
      tfcClient.getHostInfos(searchCriteria);
      params = params.append('test_harnesses', 'tf');
      expect(httpClientSpy.get)
          .toHaveBeenCalledWith(`${tfcClient.tfcApiUrl}/hosts`, {params});
      expect(httpClientSpy.get).toHaveBeenCalledTimes(1);
    });

    it('calls API with testHarnessVersions correctly', () => {
      const searchCriteria = {testHarnessVersions: ['1.0']};
      tfcClient.getHostInfos(searchCriteria);
      params = params.append('test_harness_versions', '1.0');
      expect(httpClientSpy.get)
          .toHaveBeenCalledWith(`${tfcClient.tfcApiUrl}/hosts`, {params});
      expect(httpClientSpy.get).toHaveBeenCalledTimes(1);
    });

    it('calls API with pools correctly', () => {
      const searchCriteria = {pools: ['pool-1']};
      tfcClient.getHostInfos(searchCriteria);
      params = params.append('pools', 'pool-1');
      expect(httpClientSpy.get)
          .toHaveBeenCalledWith(`${tfcClient.tfcApiUrl}/hosts`, {params});
      expect(httpClientSpy.get).toHaveBeenCalledTimes(1);
    });

    it('calls API with hostStates correctly', () => {
      const searchCriteria = {
        hostStates: [tfcModels.HostState.RUNNING, tfcModels.HostState.KILLING],
      };
      tfcClient.getHostInfos(searchCriteria);
      params = params.append('host_states', tfcModels.HostState.RUNNING)
                   .append('host_states', tfcModels.HostState.KILLING);
      expect(httpClientSpy.get)
          .toHaveBeenCalledWith(`${tfcClient.tfcApiUrl}/hosts`, {params});
      expect(httpClientSpy.get).toHaveBeenCalledTimes(1);
    });

    it('calls API with recoveryStates correctly', () => {
      const searchCriteria = {
        recoveryStates:
            [tfcModels.RecoveryState.ASSIGNED, tfcModels.RecoveryState.FIXED],
      };
      tfcClient.getHostInfos(searchCriteria);
      params =
          params.append('recovery_states', tfcModels.RecoveryState.ASSIGNED)
              .append('recovery_states', tfcModels.RecoveryState.FIXED);
      expect(httpClientSpy.get)
          .toHaveBeenCalledWith(`${tfcClient.tfcApiUrl}/hosts`, {params});
      expect(httpClientSpy.get).toHaveBeenCalledTimes(1);
    });

    it('calls API with extraInfo correctly', () => {
      const searchCriteria = {extraInfo: ['key:value']};
      tfcClient.getHostInfos(searchCriteria);
      params = params.append('flated_extra_info', 'key:value');
      expect(httpClientSpy.get)
          .toHaveBeenCalledWith(`${tfcClient.tfcApiUrl}/hosts`, {params});
      expect(httpClientSpy.get).toHaveBeenCalledTimes(1);
    });
  });

  describe('queryDeviceInfos', () => {
    const deviceInfos = mocks.newMockDeviceInfosResponse(hostname);
    const labDeviceInfos = mocks.newMockLabDeviceInfosResponse(hostname);
    let params: HttpParams;

    beforeEach(() => {
      httpClientSpy = jasmine.createSpyObj('HttpClient', ['get']);
      tfcClient = new TfcClient(appData, httpClientSpy);
      httpClientSpy.get.and.returnValue(observableOf(deviceInfos));
      params = new HttpParams({
        fromObject: {
          'count': String(maxResults),
          'cursor': pageToken,
          'backwards': String(backwards),
        }
      });
    });

    it('calls API and parses response correctly', () => {
      const observable = tfcClient.queryDeviceInfos();
      expect(httpClientSpy.get)
          .toHaveBeenCalledWith(`${tfcClient.tfcApiUrl}/devices`, {params});
      expect(httpClientSpy.get).toHaveBeenCalledTimes(1);
      observable.subscribe((response) => {
        expect(response).toEqual(labDeviceInfos);
      });
    });

    it('calls API with lab name correctly', () => {
      const searchCriteria = {lab: 'lab-1'};
      tfcClient.queryDeviceInfos(searchCriteria);
      params = params.append('lab_name', 'lab-1');
      expect(httpClientSpy.get)
          .toHaveBeenCalledWith(`${tfcClient.tfcApiUrl}/devices`, {params});
      expect(httpClientSpy.get).toHaveBeenCalledTimes(1);
    });

    it('calls API with hostnames correctly', () => {
      const searchCriteria = {hostnames: ['host-1', 'host-2']};
      tfcClient.queryDeviceInfos(searchCriteria);
      params = params.append('hostnames', 'host-1').append('hostnames', 'host-2');
      expect(httpClientSpy.get)
          .toHaveBeenCalledWith(`${tfcClient.tfcApiUrl}/devices`, {params});
      expect(httpClientSpy.get).toHaveBeenCalledTimes(1);
    });

    it('calls API with hostGroups correctly', () => {
      const searchCriteria = {hostGroups: ['group-1', 'group-2']};
      tfcClient.queryDeviceInfos(searchCriteria);
      params = params.append('host_groups', 'group-1').append('host_groups', 'group-2');
      expect(httpClientSpy.get)
          .toHaveBeenCalledWith(`${tfcClient.tfcApiUrl}/devices`, {params});
      expect(httpClientSpy.get).toHaveBeenCalledTimes(1);
    });

    it('calls API with testHarness correctly', () => {
      const searchCriteria = {testHarness: ['tf']};
      tfcClient.queryDeviceInfos(searchCriteria);
      params = params.append('test_harnesses', 'tf');
      expect(httpClientSpy.get)
          .toHaveBeenCalledWith(`${tfcClient.tfcApiUrl}/devices`, {params});
      expect(httpClientSpy.get).toHaveBeenCalledTimes(1);
    });

    it('calls API with pools correctly', () => {
      const searchCriteria = {pools: ['pool-1']};
      tfcClient.queryDeviceInfos(searchCriteria);
      params = params.append('pools', 'pool-1');
      expect(httpClientSpy.get)
          .toHaveBeenCalledWith(`${tfcClient.tfcApiUrl}/devices`, {params});
      expect(httpClientSpy.get).toHaveBeenCalledTimes(1);
    });

    it('calls API with deviceStates correctly', () => {
      const searchCriteria = {deviceStates: [tfcModels.DeviceState.AVAILABLE]};
      tfcClient.queryDeviceInfos(searchCriteria);
      params = params.append('device_states', tfcModels.DeviceState.AVAILABLE);
      expect(httpClientSpy.get)
          .toHaveBeenCalledWith(`${tfcClient.tfcApiUrl}/devices`, {params});
      expect(httpClientSpy.get).toHaveBeenCalledTimes(1);
    });

    it('calls API with runTargets correctly', () => {
      const searchCriteria = {runTargets: ['runTarget-1', 'runTarget-2']};
      tfcClient.queryDeviceInfos(searchCriteria);
      params = params.append('run_targets', 'runTarget-1').append('run_targets', 'runTarget-2');
      expect(httpClientSpy.get)
          .toHaveBeenCalledWith(`${tfcClient.tfcApiUrl}/devices`, {params});
      expect(httpClientSpy.get).toHaveBeenCalledTimes(1);
    });

    it('calls API with deviceSerial correctly', () => {
      const searchCriteria = {deviceSerial: ['serial-1', 'serial-2']};
      tfcClient.queryDeviceInfos(searchCriteria);
      params = params.append('device_serial', 'serial-1')
          .append('device_serial', 'serial-2');
      expect(httpClientSpy.get)
          .toHaveBeenCalledWith(`${tfcClient.tfcApiUrl}/devices`, {params});
      expect(httpClientSpy.get).toHaveBeenCalledTimes(1);
    });

    it('calls API with extraInfo correctly', () => {
      const searchCriteria = {extraInfo: ['key:value']};
      tfcClient.queryDeviceInfos(searchCriteria);
      params = params.append('flated_extra_info', 'key:value');
      expect(httpClientSpy.get)
          .toHaveBeenCalledWith(`${tfcClient.tfcApiUrl}/devices`, {params});
      expect(httpClientSpy.get).toHaveBeenCalledTimes(1);
    });

    it('calls API with includeOfflineDevices correctly', () => {
      const searchCriteria = {includeOfflineDevices: false};
      tfcClient.queryDeviceInfos(searchCriteria);
      params = params.appendAll({'device_states': ONLINE_DEVICE_STATES});
      expect(httpClientSpy.get)
          .toHaveBeenCalledWith(`${tfcClient.tfcApiUrl}/devices`, {params});
      expect(httpClientSpy.get).toHaveBeenCalledTimes(1);
    });
  });

  describe('getDeviceInfo', () => {
    const deviceInfo = mocks.newMockLabDeviceInfo(serial);
    const rawDeviceInfo = mocks.newMockDeviceInfo(serial);

    beforeEach(() => {
      httpClientSpy = jasmine.createSpyObj('HttpClient', ['get']);
      tfcClient = new TfcClient(appData, httpClientSpy);
      httpClientSpy.get.and.returnValue(observableOf(rawDeviceInfo));
    });

    it('should calls device API response correctly', () => {
      const observable = tfcClient.getDeviceInfo(serial);
      expect(httpClientSpy.get)
          .toHaveBeenCalledWith(`${tfcClient.tfcApiUrl}/devices/${serial}`);
      expect(httpClientSpy.get).toHaveBeenCalledTimes(1);
      observable.subscribe((response) => {
        expect(response).toEqual(deviceInfo);
      });
    });
  });

  describe('getDeviceHistory', () => {
    const rawDeviceHistoryList = mocks.newMockDeviceInfoHistoryList();
    const deviceHistoryList =
        mttLabModels.convertToLabDeviceInfoHistoryList(rawDeviceHistoryList);

    beforeEach(() => {
      httpClientSpy = jasmine.createSpyObj('HttpClient', ['get']);
      tfcClient = new TfcClient(appData, httpClientSpy);
      httpClientSpy.get.and.returnValue(observableOf(rawDeviceHistoryList));
    });

    it('should calls API response correctly', () => {
      const observable = tfcClient.getDeviceHistory(serial);
      const params = new HttpParams({
        fromObject: {
          'count': String(maxResults),
          'cursor': pageToken,
          'backwards': String(backwards),
        }
      });
      expect(httpClientSpy.get)
          .toHaveBeenCalledWith(
              `${tfcClient.tfcApiUrl}/devices/${serial}/histories`, {params});
      expect(httpClientSpy.get).toHaveBeenCalledTimes(1);
      observable.subscribe((response) => {
        expect(response).toEqual(deviceHistoryList);
      });
    });
  });

  describe('getDeviceNotes by deviceNoteIds', () => {
    const deviceNoteIds = [101, 102];
    const mockDeviceNoteList =
        mocks.newMockDeviceNoteList(serial, deviceNoteIds);

    beforeEach(() => {
      httpClientSpy = jasmine.createSpyObj('HttpClient', ['get']);
      tfcClient = new TfcClient(appData, httpClientSpy);
      httpClientSpy.get.and.returnValue(observableOf(mockDeviceNoteList));
    });

    it('calls API correctly', () => {
      const observable = tfcClient.getDeviceNotes(serial, deviceNoteIds);
      expect(httpClientSpy.get)
          .toHaveBeenCalledWith(
              `${tfcClient.tfcApiUrl}/devices/${serial}/notes`,
              jasmine.any(Object));
      expect(httpClientSpy.get).toHaveBeenCalledTimes(1);
      observable.subscribe((response) => {
        expect(response).toEqual(mockDeviceNoteList);
      });
    });
  });

  describe('getDeviceNotes by serial', () => {
    const mockDeviceNoteList = mocks.newMockDeviceNoteList(serial);

    beforeEach(() => {
      httpClientSpy = jasmine.createSpyObj('HttpClient', ['get']);
      tfcClient = new TfcClient(appData, httpClientSpy);
      httpClientSpy.get.and.returnValue(observableOf(mockDeviceNoteList));
    });

    it('calls API correctly', () => {
      const observable = tfcClient.getDeviceNotes(serial);

      const params = new HttpParams({
        fromObject: {
          'count': String(maxResults),
          'cursor': pageToken,
          'backwards': String(backwards),
        }
      });
      expect(httpClientSpy.get)
          .toHaveBeenCalledWith(
              `${tfcClient.tfcApiUrl}/devices/${serial}/notes`, {params});
      expect(httpClientSpy.get).toHaveBeenCalledTimes(1);
      observable.subscribe((response) => {
        expect(response).toEqual(mockDeviceNoteList);
      });
    });
  });

  describe('getLabInfo', () => {
    const rawLabInfo = mocks.newMockRawLabInfo(
        'lab1', ['user1'],
        newMockHostUpdateStateSummary('5', '1', '1', '2', '0', '0', '1', '0'));

    beforeEach(() => {
      httpClientSpy = jasmine.createSpyObj('HttpClient', ['get']);
      tfcClient = new TfcClient(appData, httpClientSpy);
      httpClientSpy.get.and.returnValue(observableOf(rawLabInfo));
    });

    it('calls API and parses response correctly', () => {
      const observable = tfcClient.getLabInfo('lab1');
      const labInfo = mocks.newMockLabInfo(
          'lab1', ['user1'],
          mttLabModels.convertToHostUpdateStateSummary(
              newMockHostUpdateStateSummary(
                  '5', '1', '1', '2', '0', '0', '1', '0')));
      expect(httpClientSpy.get)
          .toHaveBeenCalledWith(`${tfcClient.tfcApiUrl}/labs/lab1`);
      expect(httpClientSpy.get).toHaveBeenCalledTimes(1);
      observable.subscribe((response) => {
        expect(response).toEqual(labInfo);
      });
    });
  });

  describe('getLabInfos', () => {
    const rawLabInfos = mocks.newMockRawLabInfosResponse();

    beforeEach(() => {
      httpClientSpy = jasmine.createSpyObj('HttpClient', ['get']);
      tfcClient = new TfcClient(appData, httpClientSpy);
      httpClientSpy.get.and.returnValue(observableOf(rawLabInfos));
    });

    it('calls API and parses response correctly', () => {
      const observable = tfcClient.getLabInfos();
      const labInfos = mocks.newMockLabInfosResponse();
      expect(httpClientSpy.get)
          .toHaveBeenCalledWith(`${tfcClient.tfcApiUrl}/labs`);
      expect(httpClientSpy.get).toHaveBeenCalledTimes(1);
      observable.subscribe((response) => {
        expect(response).toEqual(labInfos);
      });
    });
  });

  describe('getMyLabInfos', () => {
    const rawLabInfos = mocks.newMockMyRawLabInfosResponse();

    beforeEach(() => {
      httpClientSpy = jasmine.createSpyObj('HttpClient', ['get']);
      tfcClient = new TfcClient(appData, httpClientSpy);
      httpClientSpy.get.and.returnValue(observableOf(rawLabInfos));
    });

    it('calls API and parses response correctly', () => {
      const observable = tfcClient.getMyLabInfos();
      const labInfos = mocks.newMockMyLabInfosResponse();
      const params = new HttpParams().set('owner', appData.userNickname!);

      expect(httpClientSpy.get)
          .toHaveBeenCalledWith(`${tfcClient.tfcApiUrl}/labs`, {params});
      expect(httpClientSpy.get).toHaveBeenCalledTimes(1);
      observable.subscribe((response) => {
        expect(response).toEqual(labInfos);
      });

      const rawLabInfos2 = mocks.newMockRawLabInfosResponse();
      httpClientSpy.get.and.returnValue(observableOf(rawLabInfos2));
      const observable2 = tfcClient.getMyLabInfos(true);
      const labInfos2 = mocks.newMockLabInfosResponse();

      expect(httpClientSpy.get)
          .toHaveBeenCalledWith(`${tfcClient.tfcApiUrl}/labs`);
      expect(httpClientSpy.get).toHaveBeenCalledTimes(2);
      observable2.subscribe((response) => {
        expect(response).toEqual(labInfos2);
      });
    });
  });

  describe('getClusterInfo', () => {
    const updateStateSummary =
        newMockHostUpdateStateSummary('5', '1', '1', '2', '0', '0', '1', '0');
    const versionCounts = [{key: 'v1', value: '22'}, {key: 'v2', value: '1'}];
    const rawClusterInfo = mocks.newMockRawClusterInfo(
        'clsuter1', updateStateSummary, versionCounts);

    beforeEach(() => {
      httpClientSpy = jasmine.createSpyObj('HttpClient', ['get']);
      tfcClient = new TfcClient(appData, httpClientSpy);
      httpClientSpy.get.and.returnValue(observableOf(rawClusterInfo));
    });

    it('calls API and parses response correctly', () => {
      const observable = tfcClient.getClusterInfo('clsuter1');
      const clusterInfo = mocks.newMockClusterInfo(
          'clsuter1',
          mttLabModels.convertToHostUpdateStateSummary(updateStateSummary),
          versionCounts);
      expect(httpClientSpy.get)
          .toHaveBeenCalledWith(`${tfcClient.tfcApiUrl}/clusters/clsuter1`);
      expect(httpClientSpy.get).toHaveBeenCalledTimes(1);
      observable.subscribe((response) => {
        expect(response).toEqual(clusterInfo);
      });
    });
  });

  describe('getMyRecoveryHostInfos', () => {
    const rawHostInfos = mocks.newMockHostInfosResponse();
    const hostInfos = mocks.newMockLabHostInfosResponse();
    const labName = 'Lab1';
    const hostGroups = ['Group1', 'Group2'];

    beforeEach(() => {
      httpClientSpy = jasmine.createSpyObj('HttpClient', ['get']);
      tfcClient = new TfcClient(appData, httpClientSpy);
      httpClientSpy.get.and.returnValue(observableOf(rawHostInfos));
    });

    it('should calls API response correctly', () => {
      const observable = tfcClient.getMyRecoveryHostInfos(labName, hostGroups);

      let params = new HttpParams().set('assignee', appData.userNickname!);
      params = params.append('lab_name', labName);
      params = params.append('host_group', hostGroups.join(','));

      expect(httpClientSpy.get)
          .toHaveBeenCalledWith(`${tfcClient.tfcApiUrl}/hosts`, {params});
      expect(httpClientSpy.get).toHaveBeenCalledTimes(1);
      observable.subscribe((response) => {
        expect(response).toEqual(hostInfos);
      });
    });
  });

  describe('getHostNotes by hostNoteIds', () => {
    const hostNoteIds = [201, 202];
    const mockHostNoteList = mocks.newMockHostNoteList(hostname, hostNoteIds);

    beforeEach(() => {
      httpClientSpy = jasmine.createSpyObj('HttpClient', ['get']);
      tfcClient = new TfcClient(appData, httpClientSpy);
      httpClientSpy.get.and.returnValue(observableOf(mockHostNoteList));
    });

    it('calls API correctly', () => {
      const observable = tfcClient.getHostNotes(hostname, hostNoteIds);
      expect(httpClientSpy.get)
          .toHaveBeenCalledWith(
              `${tfcClient.tfcApiUrl}/hosts/${hostname}/notes`,
              jasmine.any(Object));
      expect(httpClientSpy.get).toHaveBeenCalledTimes(1);
      observable.subscribe((response) => {
        expect(response).toEqual(mockHostNoteList);
      });
    });
  });

  describe('getHostNotes by hostname', () => {
    const mockHostNoteList = mocks.newMockHostNoteList(hostname);

    beforeEach(() => {
      httpClientSpy = jasmine.createSpyObj('HttpClient', ['get']);
      tfcClient = new TfcClient(appData, httpClientSpy);
      httpClientSpy.get.and.returnValue(observableOf(mockHostNoteList));
    });

    it('calls API correctly', () => {
      const observable = tfcClient.getHostNotes(hostname);

      let params = new HttpParams({
        fromObject: {
          'count': String(maxResults),
          'cursor': pageToken,
          'backwards': String(backwards),
        }
      });
      params = params.append('include_device_notes', String(true));
      expect(httpClientSpy.get)
          .toHaveBeenCalledWith(
              `${tfcClient.tfcApiUrl}/hosts/${hostname}/notes`, {params});
      expect(httpClientSpy.get).toHaveBeenCalledTimes(1);
      observable.subscribe((response) => {
        expect(response).toEqual(mockHostNoteList);
      });
    });
  });

  describe('getHostConfigs', () => {
    const mockHostConfigList = mocks.newMockHostConfigList();

    beforeEach(() => {
      httpClientSpy = jasmine.createSpyObj('HttpClient', ['get']);
      tfcClient = new TfcClient(appData, httpClientSpy);
      httpClientSpy.get.and.returnValue(observableOf(mockHostConfigList));
    });

    it('calls API correctly', () => {
      const labName = 'lab-1';
      let params = new HttpParams({
        fromObject: {
          'count': String(maxResults),
          'cursor': pageToken,
          'backwards': String(backwards),
        }
      });
      params = params.append('lab_name', labName);

      const observable = tfcClient.getHostConfigs(labName);

      expect(httpClientSpy.get)
          .toHaveBeenCalledWith(
              `${tfcClient.tfcApiUrl}/hosts/configs`, {params});
      expect(httpClientSpy.get).toHaveBeenCalledTimes(1);
      observable.subscribe((response) => {
        expect(response).toEqual(mockHostConfigList);
      });
    });
  });

  describe('getHostResource by hostname', () => {
    const mockHostResource = mocks.newMockHostResource(hostname);

    beforeEach(() => {
      httpClientSpy = jasmine.createSpyObj('HttpClient', ['get']);
      tfcClient = new TfcClient(appData, httpClientSpy);
      httpClientSpy.get.and.returnValue(observableOf(mockHostResource));
    });

    it('calls API correctly', () => {
      const observable = tfcClient.getHostResource(hostname);
      expect(httpClientSpy.get)
          .toHaveBeenCalledWith(
              `${tfcClient.tfcApiUrl}/hosts/${hostname}/resource`);
      expect(httpClientSpy.get).toHaveBeenCalledTimes(1);
      observable.subscribe((response) => {
        expect(response).toEqual(
            mttLabModels.convertToLabHostResource(mockHostResource));
      });
    });
  });

  describe('getTestHarnessImages', () => {
    const mockTestHarnessImageList = mocks.newMockTestHarnessImageList();

    beforeEach(() => {
      httpClientSpy = jasmine.createSpyObj('HttpClient', ['get']);
      tfcClient = new TfcClient(appData, httpClientSpy);
      httpClientSpy.get.and.returnValue(observableOf(mockTestHarnessImageList));
    });

    it('calls API correctly', () => {
      const tagPrefix = 'versionPrefix';
      let params = new HttpParams({
        fromObject: {
          'count': String(maxResults),
          'cursor': pageToken,
          'backwards': String(backwards),
        }
      });
      params = params.append('tag_prefix', tagPrefix);

      const observable = tfcClient.getTestHarnessImages(tagPrefix);

      expect(httpClientSpy.get)
          .toHaveBeenCalledWith(
              `${tfcClient.tfcApiUrl}/test_harness_images`, {params});
      expect(httpClientSpy.get).toHaveBeenCalledTimes(1);
      observable.subscribe((response) => {
        expect(response).toEqual(mockTestHarnessImageList);
      });
    });
  });

  describe('getOfflineHostInfos', () => {
    const labName = 'lab1';
    const hostInfos = mocks.newMockOfflineHostInfosByLabResponse(labName);
    const labHostInfos = mocks.newMockLabOfflineHostInfosByLabResponse(labName);

    beforeEach(() => {
      httpClientSpy = jasmine.createSpyObj('HttpClient', ['get']);
      tfcClient = new TfcClient(appData, httpClientSpy);
      httpClientSpy.get.and.returnValue(observableOf(hostInfos));
    });

    it('calls API correctly', () => {
      const timestamp = new Date();
      const timestampOperator = 'LESS_THAN_OR_EQUAL';
      const observable =
          tfcClient.getOfflineHostInfos(labName, timestamp, timestampOperator);
      const params =
          tfcClient.getHttpParams(tfcModels.DEFAULT_ALL_COUNT, '', false)
              .append('lab_name', labName)
              .append('is_bad', 'true')
              .append('timestamp.milliseconds', timestamp.getTime().toString())
              .append('timestamp_operator', timestampOperator);

      expect(httpClientSpy.get)
          .toHaveBeenCalledWith(`${tfcClient.tfcApiUrl}/hosts`, {params});
      expect(httpClientSpy.get).toHaveBeenCalledTimes(1);
      observable.subscribe((response) => {
        expect(response).toEqual(labHostInfos);
      });
    });
  });

  describe('createOrUpdateNote', () => {
    beforeEach(() => {
      httpClientSpy = jasmine.createSpyObj('HttpClient', ['post']);
      httpClientSpy.post.and.returnValue(observableOf({}));
      tfcClient = new TfcClient(appData, httpClientSpy);
    });

    it('calls API for host correctly', () => {
      const context = AnalyticsContext.create('host_note', 'create');
      const noteInfo: mttLabModels.CreateOrUpdateNoteInfo = {
        user: appData.userNickname,
        hostname: 'host1',
        labName: 'lab1',
        message: 'message1',
        offlineReason: 'reason1',
        offlineReasonId: 1,
        recoveryAction: 'action1',
        recoveryActionId: 1,
        noteType: mttLabModels.NoteType.HOST,
      };

      tfcClient.createOrUpdateNote(noteInfo);

      const body: tfcModels.CreateOrUpdateNote = {
        user: appData.userNickname || '',
        lab_name: noteInfo.labName,
        id: noteInfo.id || undefined,
        message: noteInfo.message || '',
        offline_reason: noteInfo.offlineReason || '',
        offline_reason_id: noteInfo.offlineReasonId || undefined,
        recovery_action: noteInfo.recoveryAction || '',
        recovery_action_id: noteInfo.recoveryActionId || undefined,
        hostname: noteInfo.hostname || '',
      };

      expect(httpClientSpy.post)
          .toHaveBeenCalledWith(
              `${tfcClient.tfcApiUrl}/hosts/${noteInfo.hostname}/notes`, body,
              {context});
      expect(httpClientSpy.post).toHaveBeenCalledTimes(1);
    });

    it('calls API for device correctly', () => {
      const context = AnalyticsContext.create('device_note', 'create');
      const noteInfo: mttLabModels.CreateOrUpdateNoteInfo = {
        user: appData.userNickname,
        deviceSerial: 'device1',
        labName: 'lab1',
        message: 'message1',
        offlineReason: 'reason1',
        offlineReasonId: 1,
        recoveryAction: 'action1',
        recoveryActionId: 1,
        noteType: mttLabModels.NoteType.DEVICE,
        hostname: 'host1',
      };

      tfcClient.createOrUpdateNote(noteInfo);

      const body: tfcModels.CreateOrUpdateNote = {
        user: appData.userNickname || '',
        lab_name: noteInfo.labName,
        id: noteInfo.id || undefined,
        message: noteInfo.message || '',
        offline_reason: noteInfo.offlineReason || '',
        offline_reason_id: noteInfo.offlineReasonId || undefined,
        recovery_action: noteInfo.recoveryAction || '',
        recovery_action_id: noteInfo.recoveryActionId || undefined,
        device_serial: noteInfo.deviceSerial || '',
        hostname: noteInfo.hostname || '',
      };

      expect(httpClientSpy.post)
          .toHaveBeenCalledWith(
              `${tfcClient.tfcApiUrl}/devices/${noteInfo.deviceSerial}/notes`,
              body, {context});
      expect(httpClientSpy.post).toHaveBeenCalledTimes(1);
    });
  });

  describe('removeDevice', () => {
    beforeEach(() => {
      httpClientSpy = jasmine.createSpyObj('HttpClient', ['post']);
      httpClientSpy.post.and.returnValue(observableOf({}));
      tfcClient = new TfcClient(appData, httpClientSpy);
    });

    it('calls API correctly', () => {
      const deviceSerial = 'device1';
      const hostname = 'host1';

      tfcClient.removeDevice(deviceSerial, hostname);

      const context = AnalyticsContext.create('device', 'remove');
      let params = new HttpParams();
      params = params.append('hostname', hostname);

      expect(httpClientSpy.post)
          .toHaveBeenCalledWith(
              `${tfcClient.tfcApiUrl}/devices/${deviceSerial}/remove`, null,
              {params, context});
      expect(httpClientSpy.post).toHaveBeenCalledTimes(1);
    });
  });

  describe('removeHost', () => {
    beforeEach(() => {
      httpClientSpy = jasmine.createSpyObj('HttpClient', ['post']);
      httpClientSpy.post.and.returnValue(observableOf({}));
      tfcClient = new TfcClient(appData, httpClientSpy);
    });

    it('calls API correctly', () => {
      const hostname = 'host1';

      tfcClient.removeHost(hostname);

      const context = AnalyticsContext.create('host', 'remove');

      expect(httpClientSpy.post)
          .toHaveBeenCalledWith(
              `${tfcClient.tfcApiUrl}/hosts/${hostname}/remove`, null,
              {context});
      expect(httpClientSpy.post).toHaveBeenCalledTimes(1);
    });
  });

  describe('updatePredefinedMessage', () => {
    const id = 2;
    const predefinedMessage = mocks.newMockPredefinedMessage(id);

    beforeEach(() => {
      httpClientSpy = jasmine.createSpyObj('HttpClient', ['patch']);
      httpClientSpy.patch.and.returnValue(observableOf(predefinedMessage));
      tfcClient = new TfcClient(appData, httpClientSpy);
    });

    it('calls API correctly', () => {
      const content = 'update content text';

      tfcClient.updatePredefinedMessage(id, content);

      const context = AnalyticsContext.create('predefined_message', 'update');
      const body = {
        'content': content,
      };

      expect(httpClientSpy.patch)
          .toHaveBeenCalledWith(
              `${tfcClient.tfcApiUrl}/predefined_messages/${id}`, body,
              {context});
      expect(httpClientSpy.patch).toHaveBeenCalledTimes(1);
    });
  });

  describe('createPredefinedMessage', () => {
    const id = 3;
    const predefinedMessage = mocks.newMockPredefinedMessage(id);

    beforeEach(() => {
      httpClientSpy = jasmine.createSpyObj('HttpClient', ['post']);
      httpClientSpy.post.and.returnValue(observableOf(predefinedMessage));
      tfcClient = new TfcClient(appData, httpClientSpy);
    });

    it('calls API correctly', () => {
      const predefinedMessageInfo: mttLabModels.CreatePredefinedMessageInfo = {
        labName: 'lab1',
        content: 'content text',
        predefinedMessageType:
            tfcModels.PredefinedMessageType.DEVICE_OFFLINE_REASON,
      };

      tfcClient.createPredefinedMessage(predefinedMessageInfo);

      const context = AnalyticsContext.create('predefined_message', 'create');

      const body = {
        'lab_name': predefinedMessageInfo.labName,
        'type': predefinedMessageInfo.predefinedMessageType,
        'content': predefinedMessageInfo.content,
      };

      expect(httpClientSpy.post)
          .toHaveBeenCalledWith(
              `${tfcClient.tfcApiUrl}/predefined_messages`, body, {context});
      expect(httpClientSpy.post).toHaveBeenCalledTimes(1);
    });
  });

  describe('deletePredefinedMessage', () => {
    beforeEach(() => {
      httpClientSpy = jasmine.createSpyObj('HttpClient', ['delete']);
      httpClientSpy.delete.and.returnValue(observableOf({}));
      tfcClient = new TfcClient(appData, httpClientSpy);
    });

    it('calls API correctly', () => {
      const id = 4;

      tfcClient.deletePredefinedMessage(id);

      const context = AnalyticsContext.create('predefined_message', 'delete');

      expect(httpClientSpy.delete)
          .toHaveBeenCalledWith(
              `${tfcClient.tfcApiUrl}/predefined_messages/${id}`, {context});
      expect(httpClientSpy.delete).toHaveBeenCalledTimes(1);
    });
  });

  describe('batchGetDevicesLatestNotes', () => {
    const deviceSerials = ['device1', 'device2', 'device3'];
    let params = new HttpParams();
    for (const deviceSerial of deviceSerials) {
      params = params.append('device_serials', deviceSerial);
    }
    const noteList = mocks.newMockDevicesLatestNoteList(deviceSerials);
    beforeEach(() => {
      httpClientSpy = jasmine.createSpyObj('HttpClient', ['get']);
      tfcClient = new TfcClient(appData, httpClientSpy);
      httpClientSpy.get.and.returnValue(observableOf(noteList));
    });

    it('should calls API response correctly', () => {
      const observable = tfcClient.batchGetDevicesLatestNotes(deviceSerials);
      expect(httpClientSpy.get)
          .toHaveBeenCalledWith(
              `${tfcClient.tfcApiUrl}/devices/latest_notes:batchGet`, {params});
      expect(httpClientSpy.get).toHaveBeenCalledTimes(1);
      observable.subscribe((response) => {
        expect(response).toEqual(noteList);
      });
    });
  });

  describe('getFilterHintList', () => {
    const filterHintType = tfcModels.FilterHintType.LAB;
    const filterHintList = mocks.newMockFilterHintList(filterHintType, 10);

    beforeEach(() => {
      httpClientSpy = jasmine.createSpyObj('HttpClient', ['get']);
      tfcClient = new TfcClient(appData, httpClientSpy);
      httpClientSpy.get.and.returnValue(observableOf(filterHintList));
    });

    it('should calls API correctly', () => {
      const observable = tfcClient.getFilterHintList(filterHintType);
      const params = new HttpParams().set('type', filterHintType);
      expect(httpClientSpy.get)
          .toHaveBeenCalledWith(`${tfcClient.tfcApiUrl}/filterHints`, {params});
      expect(httpClientSpy.get).toHaveBeenCalledTimes(1);
      observable.subscribe((response) => {
        expect(response).toEqual(filterHintList);
      });
    });
  });

  describe('batchSetHostsRecoveryStates', () => {
    beforeEach(() => {
      httpClientSpy = jasmine.createSpyObj('HttpClient', ['post']);
      httpClientSpy.post.and.returnValue(observableOf({}));
      tfcClient = new TfcClient(appData, httpClientSpy);
    });

    it('should assign hosts correctly', () => {
      const assignee = appData.userNickname;
      const hostRecoveryStateRequests = [
        {
          hostname: 'host-1',
          recovery_state: tfcModels.RecoveryState.ASSIGNED,
          assignee
        } as tfcModels.HostRecoveryStateRequest,
        {
          hostname: 'host-3',
          recovery_state: tfcModels.RecoveryState.ASSIGNED,
          assignee
        } as tfcModels.HostRecoveryStateRequest,
      ];

      tfcClient.batchSetHostsRecoveryStates(hostRecoveryStateRequests);

      const context = AnalyticsContext.create('hosts', 'setRecoveryStates');

      const body = {
        host_recovery_state_requests: hostRecoveryStateRequests,
      } as tfcModels.HostRecoveryStateRequests;

      expect(httpClientSpy.post)
          .toHaveBeenCalledWith(
              tfcClient.batchSetHostsRecoveryStatesUrl, body, {context});
      expect(httpClientSpy.post).toHaveBeenCalledTimes(1);
    });

    it('should mark hosts as verified correctly', () => {
      const hostRecoveryStateRequests = [
        {
          hostname: 'host-1',
          recovery_state: tfcModels.RecoveryState.VERIFIED,
        } as tfcModels.HostRecoveryStateRequest,
        {
          hostname: 'host-3',
          recovery_state: tfcModels.RecoveryState.VERIFIED,
        } as tfcModels.HostRecoveryStateRequest,
      ];

      tfcClient.batchSetHostsRecoveryStates(hostRecoveryStateRequests);

      const context = AnalyticsContext.create('hosts', 'setRecoveryStates');

      const body = {
        host_recovery_state_requests: hostRecoveryStateRequests,
      } as tfcModels.HostRecoveryStateRequests;

      expect(httpClientSpy.post)
          .toHaveBeenCalledWith(
              tfcClient.batchSetHostsRecoveryStatesUrl, body, {context});
      expect(httpClientSpy.post).toHaveBeenCalledTimes(1);
    });
  });

  describe('batchSetDevicesRecoveryStates', () => {
    beforeEach(() => {
      httpClientSpy = jasmine.createSpyObj('HttpClient', ['post']);
      httpClientSpy.post.and.returnValue(observableOf({}));
      tfcClient = new TfcClient(appData, httpClientSpy);
    });

    it('should mark devices as fixed correctly', () => {
      const deviceRecoveryStateRequests = [
        {
          hostname: 'host-1',
          device_serial: 'device1',
          recovery_state: tfcModels.RecoveryState.FIXED,
        } as tfcModels.DeviceRecoveryStateRequest,
        {
          hostname: 'host-1',
          device_serial: 'device2',
          recovery_state: tfcModels.RecoveryState.FIXED,
        } as tfcModels.DeviceRecoveryStateRequest,
      ];

      tfcClient.batchSetDevicesRecoveryStates(deviceRecoveryStateRequests);

      const context = AnalyticsContext.create('devices', 'setRecoveryStates');

      const body = {
        device_recovery_state_requests: deviceRecoveryStateRequests,
      } as tfcModels.DeviceRecoveryStateRequests;

      expect(httpClientSpy.post)
          .toHaveBeenCalledWith(
              tfcClient.batchSetDevicesRecoveryStatesUrl, body, {context});
      expect(httpClientSpy.post).toHaveBeenCalledTimes(1);
    });

    it('should mark devices as unknown correctly', () => {
      const deviceRecoveryStateRequests = [
        {
          hostname: 'host-1',
          device_serial: 'device1',
          recovery_state: tfcModels.RecoveryState.UNKNOWN,
        } as tfcModels.DeviceRecoveryStateRequest,
        {
          hostname: 'host-1',
          device_serial: 'device2',
          recovery_state: tfcModels.RecoveryState.UNKNOWN,
        } as tfcModels.DeviceRecoveryStateRequest,
      ];

      tfcClient.batchSetDevicesRecoveryStates(deviceRecoveryStateRequests);

      const context = AnalyticsContext.create('devices', 'setRecoveryStates');

      const body = {
        device_recovery_state_requests: deviceRecoveryStateRequests,
      } as tfcModels.DeviceRecoveryStateRequests;

      expect(httpClientSpy.post)
          .toHaveBeenCalledWith(
              tfcClient.batchSetDevicesRecoveryStatesUrl, body, {context});
      expect(httpClientSpy.post).toHaveBeenCalledTimes(1);
    });
  });

  describe('batchCreateOrUpdateDevicesNotesWithPredefinedMessage', () => {
    beforeEach(() => {
      httpClientSpy = jasmine.createSpyObj('HttpClient', ['post']);
      httpClientSpy.post.and.returnValue(observableOf({}));
      tfcClient = new TfcClient(appData, httpClientSpy);
    });

    it('should add notes correctly', () => {
      const notesInfo: mttLabModels.BatchCreateOrUpdateNotesInfo = {
        lab_name: '',
        notes: [
          {device_serial: '1'},
          {device_serial: '2'},
        ],
        offline_reason: 'reason1',
        recovery_action_id: 123,
      };

      tfcClient.batchCreateOrUpdateDevicesNotesWithPredefinedMessage(notesInfo);

      const context =
          AnalyticsContext.create('device_note', 'batchCreateOrUpdateNotes');

      notesInfo.user = appData.userNickname;
      const body = notesInfo;

      expect(httpClientSpy.post)
          .toHaveBeenCalledWith(
              `${
                  tfcClient
                      .tfcApiUrl}/devices/notes:batchUpdateNotesWithPredefinedMessage`,
              body, {context});
      expect(httpClientSpy.post).toHaveBeenCalledTimes(1);
    });
  });

  describe('batchCreateOrUpdateHostsNotesWithPredefinedMessage', () => {
    beforeEach(() => {
      httpClientSpy = jasmine.createSpyObj('HttpClient', ['post']);
      httpClientSpy.post.and.returnValue(observableOf({}));
      tfcClient = new TfcClient(appData, httpClientSpy);
    });

    it('should add notes correctly', () => {
      const notesInfo: mttLabModels.BatchCreateOrUpdateNotesInfo = {
        lab_name: '',
        notes: [
          {hostname: 'host1'},
          {hostname: 'host2'},
        ],
        offline_reason: 'reason1',
        recovery_action_id: 123,
      };

      tfcClient.batchCreateOrUpdateHostsNotesWithPredefinedMessage(notesInfo);

      const context =
          AnalyticsContext.create('host_note', 'batchCreateOrUpdateNotes');

      notesInfo.user = appData.userNickname;
      const body = notesInfo;

      expect(httpClientSpy.post)
          .toHaveBeenCalledWith(
              `${
                  tfcClient
                      .tfcApiUrl}/hosts/notes:batchUpdateNotesWithPredefinedMessage`,
              body, {context});
      expect(httpClientSpy.post).toHaveBeenCalledTimes(1);
    });
  });

  describe('batchbatchUpdateHostMetadata', () => {
    beforeEach(() => {
      httpClientSpy = jasmine.createSpyObj('HttpClient', ['post']);
      httpClientSpy.post.and.returnValue(observableOf({}));
      tfcClient = new TfcClient(appData, httpClientSpy);
    });

    it('updates metadata correctly', () => {
      const requestBody = mocks.newMockBatchUpdateHostMetadataRequest(
          [hostname], harnemssImage, appData.userNickname);
      tfcClient.batchUpdateHostMetadata(requestBody);

      const context =
          AnalyticsContext.create('hosts', 'batchUpdateHostMetadata');

      expect(httpClientSpy.post)
          .toHaveBeenCalledWith(
              `${tfcClient.tfcApiUrl}/hosts/hostMetadata:batchUpdate`,
              requestBody, {context});
      expect(httpClientSpy.post).toHaveBeenCalledTimes(1);
    });

    it('updates metadata in splices correctly', () => {
      const requestBody = mocks.newMockBatchUpdateHostMetadataRequest(
          ['h1', 'h2', 'h3'], harnemssImage, appData.userNickname);
      const requestBodySlice0 = mocks.newMockBatchUpdateHostMetadataRequest(
          ['h1', 'h2'], harnemssImage, appData.userNickname);
      const requestBodySlice1 = mocks.newMockBatchUpdateHostMetadataRequest(
          ['h3'], harnemssImage, appData.userNickname);
      tfcClient.batchUpdateHostMetadata(requestBody, 2);

      expect(httpClientSpy.post).toHaveBeenCalledTimes(2);
      expect(httpClientSpy.post.calls.all()[0].args[1])
          .toEqual(requestBodySlice0);
      expect(httpClientSpy.post.calls.all()[1].args[1])
          .toEqual(requestBodySlice1);
    });
  });

  describe('checkUserPermission', () => {
    const mockUserPermission: tfcModels.UserPermission = {isAdmin: true};

    beforeEach(() => {
      httpClientSpy = jasmine.createSpyObj('HttpClient', ['get']);
      tfcClient = new TfcClient(appData, httpClientSpy);
      httpClientSpy.get.and.returnValue(observableOf(mockUserPermission));
    });

    it('calls API correctly', () => {
      const observable = tfcClient.checkUserPermission();
      const params = new HttpParams().set('email', appData.email!);

      expect(httpClientSpy.get)
          .toHaveBeenCalledWith(
              `${tfcClient.tfcApiUrl}/admins/check`, {params});
      expect(httpClientSpy.get).toHaveBeenCalledTimes(1);
      observable.subscribe((response) => {
        expect(response).toEqual(mockUserPermission);
      });
    });
  });

  describe('batchDeleteHostNotes', () => {
    beforeEach(() => {
      httpClientSpy = jasmine.createSpyObj('HttpClient', ['delete']);
      httpClientSpy.delete.and.returnValue(observableOf({}));
      tfcClient = new TfcClient(appData, httpClientSpy);
    });

    it('calls API correctly', () => {
      const hostname = 'host1';
      const noteIds = [1, 2, 3];

      tfcClient.batchDeleteHostNotes(hostname, noteIds);

      let params = new HttpParams();
      for (const id of noteIds) {
        params = params.append('ids', id.toString());
      }

      expect(httpClientSpy.delete)
          .toHaveBeenCalledWith(
              `${tfcClient.tfcApiUrl}/hosts/${hostname}/notes`, {params});
      expect(httpClientSpy.delete).toHaveBeenCalledTimes(1);
    });
  });

  describe('batchDeleteDeviceNotes', () => {
    beforeEach(() => {
      httpClientSpy = jasmine.createSpyObj('HttpClient', ['delete']);
      httpClientSpy.delete.and.returnValue(observableOf({}));
      tfcClient = new TfcClient(appData, httpClientSpy);
    });

    it('calls API correctly', () => {
      const deviceSerial = 'device1';
      const noteIds = [1, 2, 3];

      tfcClient.batchDeleteDeviceNotes(deviceSerial, noteIds);

      let params = new HttpParams();
      for (const id of noteIds) {
        params = params.append('ids', id.toString());
      }

      expect(httpClientSpy.delete)
          .toHaveBeenCalledWith(
              `${tfcClient.tfcApiUrl}/devices/${deviceSerial}/notes`, {params});
      expect(httpClientSpy.delete).toHaveBeenCalledTimes(1);
    });
  });
});
