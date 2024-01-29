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

import * as testUtil from '../testing/mtt_mocks';

import {AuthService, REDIRECT_URI} from './auth_service';
import {BuildClient, MTT_API_URL, MttClient, NetdataClient, TestRunActionClient} from './mtt_client';
import {Build, BuildChannelList, BuildList, TestPlanList, TestRunAction, TestRunActionRefList, XtsRequirementsDetectionRequest} from './mtt_models';

describe('MttClient', () => {
  let httpClientSpy: jasmine.SpyObj<HttpClient>;
  let authServiceSpy: jasmine.SpyObj<AuthService>;
  let mttClient: MttClient;

  beforeEach(() => {
    httpClientSpy = jasmine.createSpyObj<HttpClient>(
        'HttpClient', ['get', 'post', 'put', 'delete']);
    authServiceSpy = jasmine.createSpyObj<AuthService>(
        'AuthService', ['getAuthorizationCode']);
    mttClient = new MttClient(httpClientSpy, authServiceSpy);
  });

  describe('authorizeBuildChannel', () => {
    const AUTH_INFO = {url: 'auth_url', is_manual: false};
    const BUILD_CHANNEL_ID = 'build_channel_id';
    const CODE = 'code';

    beforeEach(() => {
      httpClientSpy.get.and.returnValue(observableOf(AUTH_INFO));
      authServiceSpy.getAuthorizationCode.and.returnValue(observableOf(CODE));
      httpClientSpy.post.and.returnValue(observableOf());
    });

    it('makes right sequence of API requests', () => {
      mttClient.authorizeBuildChannel(BUILD_CHANNEL_ID).subscribe();
      // Fetches authorization information
      const params = new HttpParams().set('redirect_uri', REDIRECT_URI);
      expect(httpClientSpy.get)
          .toHaveBeenCalledWith(
              '/_ah/api/mtt/v1/build_channels/build_channel_id/auth', {params});
      expect(httpClientSpy.get).toHaveBeenCalledTimes(1);
      // Obtains authorization code from user
      expect(authServiceSpy.getAuthorizationCode)
          .toHaveBeenCalledWith(AUTH_INFO);
      expect(authServiceSpy.getAuthorizationCode).toHaveBeenCalledTimes(1);
      // Sends authorization code
      expect(httpClientSpy.post)
          .toHaveBeenCalledWith(
              '/_ah/api/mtt/v1/build_channels/build_channel_id/auth',
              {'redirect_uri': REDIRECT_URI, 'code': CODE},
              jasmine.any(Object));
      expect(httpClientSpy.post).toHaveBeenCalledTimes(1);
    });
  });

  describe('authorizeBuildChannelWithServiceAccount', () => {
    it('can authorize build channel with service account', done => {
      httpClientSpy.put.and.returnValue(observableOf(null));
      mttClient.authorizeBuildChannelWithServiceAccount('id', new Blob(['key']))
          .subscribe(() => {
            // Uploads key content
            expect(httpClientSpy.put)
                .toHaveBeenCalledWith(
                    '/_ah/api/mtt/v1/build_channels/id/auth', {value: 'key'},
                    jasmine.any(Object));
            expect(httpClientSpy.put).toHaveBeenCalledTimes(1);
            done();
          });
    });
  });

  describe('unauthorizeBuildChannel', () => {
    it('can revoke build channel authorization', () => {
      httpClientSpy.delete.and.returnValue(observableOf());
      mttClient.unauthorizeBuildChannel('id').subscribe();
      expect(httpClientSpy.delete)
          .toHaveBeenCalledWith(
              '/_ah/api/mtt/v1/build_channels/id/auth', jasmine.any(Object));
      expect(httpClientSpy.delete).toHaveBeenCalledTimes(1);
    });
  });

  describe('listBuildItem', () => {
    const BUILD_ITEM_LIST = testUtil.newMockBuildItemList();

    beforeEach(() => {
      httpClientSpy.get.and.returnValue(observableOf(BUILD_ITEM_LIST));
    });

    it('calls API and parses response correctly', () => {
      const id = 'test_id';
      const path = 'test_path';
      const observable = mttClient.listBuildItems(id, path);
      expect(httpClientSpy.get)
          .toHaveBeenCalledWith(
              `${MTT_API_URL}/build_channels/${id}/build_items`,
              jasmine.any(Object));
      expect(httpClientSpy.get).toHaveBeenCalledTimes(1);
      observable.subscribe((response) => {
        expect(response).toEqual(jasmine.objectContaining(BUILD_ITEM_LIST));
      });
    });
  });

  describe('deleteBuildItem', () => {
    beforeEach(() => {
      httpClientSpy.delete.and.returnValue(observableOf({}));
    });

    it('calls API correctly', () => {
      const id = 'build_channel_id';
      const path = 'path';
      const observable = mttClient.deleteBuildItem(id, path);
      expect(httpClientSpy.delete)
          .toHaveBeenCalledWith(
              `${MTT_API_URL}/build_channels/${id}/build_items`,
              jasmine.any(Object));
      expect(httpClientSpy.delete).toHaveBeenCalledTimes(1);
      observable.subscribe((response) => {
        expect(response).toEqual({});
      });
    });
  });

  describe('lookupBuildItem', () => {
    const BUILD_ITEM = testUtil.newMockBuildItem();

    beforeEach(() => {
      httpClientSpy.get.and.returnValue(observableOf(BUILD_ITEM));
    });

    it('calls API correctly', () => {
      const url = 'http://foo.com/bar/zzz';
      const observable = mttClient.lookupBuildItem(url);
      expect(httpClientSpy.get)
          .toHaveBeenCalledWith(
              `${MTT_API_URL}/build_channels/build_item_lookup`,
              jasmine.any(Object));
      expect(httpClientSpy.get).toHaveBeenCalledTimes(1);
      observable.subscribe((response) => {
        expect(response).toEqual(BUILD_ITEM);
      });
    });
  });

  describe('getBuildChannels', () => {
    const BUILD_CHANNELS:
        BuildChannelList = {build_channels: [testUtil.newMockBuildChannel()]};
    const url = `${MTT_API_URL}/build_channels`;

    beforeEach(() => {
      httpClientSpy.get.and.returnValue(observableOf(BUILD_CHANNELS));
    });

    it('calls API correctly', () => {
      mttClient.getBuildChannels();
      expect(httpClientSpy.get).toHaveBeenCalledWith(url);
      expect(httpClientSpy.get).toHaveBeenCalledTimes(1);
    });

    it('parses API response correctly', () => {
      const observable = mttClient.getBuildChannels();
      observable.subscribe((response) => {
        expect(response).toEqual(BUILD_CHANNELS);
      });
    });
  });

  describe('getDeviceActionList', () => {
    const DEVICE_ACTION_LIST = testUtil.newMockDeviceActionList();

    beforeEach(() => {
      httpClientSpy.get.and.returnValue(
          observableOf({device_actions: DEVICE_ACTION_LIST}));
    });

    it('calls API and parses response correctly', () => {
      const observable = mttClient.getDeviceActionList();
      expect(httpClientSpy.get)
          .toHaveBeenCalledWith(`${MTT_API_URL}/device_actions`);
      expect(httpClientSpy.get).toHaveBeenCalledTimes(1);
      observable.subscribe((response) => {
        expect(response).toEqual(
            jasmine.objectContaining({device_actions: DEVICE_ACTION_LIST}));
      });
    });
  });

  describe('getDeviceAction', () => {
    const DEVICE_ACTION = testUtil.newMockDeviceAction();

    beforeEach(() => {
      httpClientSpy.get.and.returnValue(observableOf(DEVICE_ACTION));
    });

    it('calls API and parses response correctly', () => {
      const observable = mttClient.getDeviceAction(DEVICE_ACTION.id);
      expect(httpClientSpy.get)
          .toHaveBeenCalledWith(
              `${MTT_API_URL}/device_actions/${DEVICE_ACTION.id}`);
      expect(httpClientSpy.get).toHaveBeenCalledTimes(1);
      observable.subscribe((response) => {
        expect(response).toEqual(jasmine.objectContaining(DEVICE_ACTION));
      });
    });
  });

  describe('createDeviceAction', () => {
    const DEVICE_ACTION = testUtil.newMockDeviceAction();

    beforeEach(() => {
      httpClientSpy.post.and.returnValue(observableOf(DEVICE_ACTION));
    });

    it('calls API and parses response correctly', () => {
      const observable = mttClient.createDeviceAction(DEVICE_ACTION);
      expect(httpClientSpy.post)
          .toHaveBeenCalledWith(
              `${MTT_API_URL}/device_actions`, DEVICE_ACTION,
              jasmine.any(Object));
      expect(httpClientSpy.post).toHaveBeenCalledTimes(1);
      observable.subscribe((response) => {
        expect(response).toEqual(jasmine.objectContaining(DEVICE_ACTION));
      });
    });
  });

  describe('updateDeviceAction', () => {
    const DEVICE_ACTION = testUtil.newMockDeviceAction();

    beforeEach(() => {
      httpClientSpy.put.and.returnValue(observableOf(DEVICE_ACTION));
    });

    it('calls API and parses response correctly', () => {
      const observable =
          mttClient.updateDeviceAction(DEVICE_ACTION.id, DEVICE_ACTION);
      expect(httpClientSpy.put)
          .toHaveBeenCalledWith(
              `${MTT_API_URL}/device_actions/${DEVICE_ACTION.id}`,
              DEVICE_ACTION, jasmine.any(Object));
      expect(httpClientSpy.put).toHaveBeenCalledTimes(1);
      observable.subscribe((response) => {
        expect(response).toEqual(jasmine.objectContaining(DEVICE_ACTION));
      });
    });
  });

  describe('createNewTestRunRequest', () => {
    const newtestRun = testUtil.newMockNewTestRunRequest();
    beforeEach(() => {
      httpClientSpy.post.and.returnValue(observableOf(newtestRun));
    });

    it('calls API and parses response correctly', () => {
      const observable = mttClient.createNewTestRunRequest(newtestRun);
      expect(httpClientSpy.post)
          .toHaveBeenCalledWith(
              `${MTT_API_URL}/test_runs`, newtestRun, jasmine.any(Object));
      expect(httpClientSpy.post).toHaveBeenCalledTimes(1);
      observable.subscribe((response) => {
        expect(response).toEqual(jasmine.objectContaining(newtestRun));
      });
    });
  });

  describe('getNodeConfig', () => {
    const nodeConfig = testUtil.newMockNodeConfig();
    beforeEach(() => {
      httpClientSpy.get.and.returnValue(observableOf(nodeConfig));
    });

    it('calls API and parses response correctly', () => {
      const observable = mttClient.getNodeConfig();
      expect(httpClientSpy.get)
          .toHaveBeenCalledWith(`${MTT_API_URL}/node_config`);
      expect(httpClientSpy.get).toHaveBeenCalledTimes(1);
      observable.subscribe((response) => {
        expect(response).toEqual(nodeConfig);
      });
    });
  });

  describe('updateNodeConfig', () => {
    const nodeConfig = testUtil.newMockNodeConfig();
    beforeEach(() => {
      httpClientSpy.put.and.returnValue(observableOf(nodeConfig));
    });

    it('calls API and parses response correctly', () => {
      const observable = mttClient.updateNodeConfig(nodeConfig);
      expect(httpClientSpy.put)
          .toHaveBeenCalledWith(
              `${MTT_API_URL}/node_config`, nodeConfig, jasmine.any(Object));
      expect(httpClientSpy.put).toHaveBeenCalledTimes(1);
      observable.subscribe((response) => {
        expect(response).toEqual(jasmine.objectContaining(nodeConfig));
      });
    });
  });

  describe('importNodeConfig', () => {
    const fileContent = 'random';
    beforeEach(() => {
      httpClientSpy.post.and.returnValue(observableOf());
    });

    it('calls API and parses response correctly', () => {
      mttClient.importNodeConfig('random');
      expect(httpClientSpy.post)
          .toHaveBeenCalledWith(
              `${MTT_API_URL}/node_config/import`, {'value': fileContent},
              jasmine.any(Object));
      expect(httpClientSpy.post).toHaveBeenCalledTimes(1);
    });
  });

  describe('exportNodeConfig', () => {
    const simpleMessage = {'value': '123'};
    beforeEach(() => {
      httpClientSpy.get.and.returnValue(observableOf(simpleMessage));
    });

    it('calls API and parses response correctly', () => {
      const observable = mttClient.exportNodeConfig();
      expect(httpClientSpy.get).toHaveBeenCalledTimes(1);
      expect(httpClientSpy.get)
          .toHaveBeenCalledWith(
              `${MTT_API_URL}/node_config/export`, jasmine.any(Object));
      observable.subscribe((response) => {
        expect(response).toEqual(jasmine.objectContaining(simpleMessage));
      });
    });
  });

  describe('getPrivateNodeConfig', () => {
    const privateNodeConfig = testUtil.newMockPrivateNodeConfig();
    beforeEach(() => {
      httpClientSpy.get.and.returnValue(observableOf(privateNodeConfig));
    });

    it('calls API and parses response correctly', () => {
      const observable = mttClient.getPrivateNodeConfig();
      expect(httpClientSpy.get)
          .toHaveBeenCalledWith(`${MTT_API_URL}/private_node_config`);
      expect(httpClientSpy.get).toHaveBeenCalledTimes(1);
      observable.subscribe((response) => {
        expect(response).toEqual(privateNodeConfig);
      });
    });
  });

  describe('updatePrivateNodeConfig', () => {
    const privateNodeConfig = testUtil.newMockPrivateNodeConfig();
    beforeEach(() => {
      httpClientSpy.put.and.returnValue(observableOf(privateNodeConfig));
    });

    it('calls API and parses response correctly', () => {
      const observable = mttClient.updatePrivateNodeConfig(privateNodeConfig);
      expect(httpClientSpy.put)
          .toHaveBeenCalledWith(
              `${MTT_API_URL}/private_node_config`, privateNodeConfig,
              jasmine.any(Object));
      expect(httpClientSpy.put).toHaveBeenCalledTimes(1);
      observable.subscribe((response) => {
        expect(response).toEqual(jasmine.objectContaining(privateNodeConfig));
      });
    });
  });

  describe('createTest', () => {
    const TEST = testUtil.newMockTest();
    beforeEach(() => {
      httpClientSpy.post.and.returnValue(observableOf(TEST));
    });

    it('calls API and parses response correctly', () => {
      const observable = mttClient.createTest(TEST);
      expect(httpClientSpy.post)
          .toHaveBeenCalledWith(
              `${MTT_API_URL}/tests`, TEST, jasmine.any(Object));
      expect(httpClientSpy.post).toHaveBeenCalledTimes(1);
      observable.subscribe((response) => {
        expect(response).toEqual(jasmine.objectContaining(TEST));
      });
    });
  });

  describe('getTest', () => {
    const TEST = testUtil.newMockTest();
    beforeEach(() => {
      httpClientSpy.get.and.returnValue(observableOf(TEST));
    });

    it('calls API and parses response correctly', () => {
      const observable = mttClient.getTest(TEST.id);
      expect(httpClientSpy.get)
          .toHaveBeenCalledWith(`${MTT_API_URL}/tests/${TEST.id}`);
      expect(httpClientSpy.get).toHaveBeenCalledTimes(1);
      observable.subscribe((response) => {
        expect(response).toEqual(jasmine.objectContaining(TEST));
      });
    });
  });

  describe('updateTest', () => {
    const TEST = testUtil.newMockTest();
    beforeEach(() => {
      httpClientSpy.put.and.returnValue(observableOf(TEST));
    });

    it('calls API and parses response correctly', () => {
      const observable = mttClient.updateTest(TEST.id, TEST);
      expect(httpClientSpy.put)
          .toHaveBeenCalledWith(
              `${MTT_API_URL}/tests/${TEST.id}`, TEST, jasmine.any(Object));
      expect(httpClientSpy.put).toHaveBeenCalledTimes(1);
      observable.subscribe((response) => {
        expect(response).toEqual(jasmine.objectContaining(TEST));
      });
    });
  });

  describe('getTestPlan', () => {
    const TEST_PLAN = testUtil.newMockTestPlan();
    beforeEach(() => {
      httpClientSpy.get.and.returnValue(observableOf(TEST_PLAN));
    });

    it('calls API and parses response correctly', () => {
      const observable = mttClient.getTestPlan(TEST_PLAN.id);
      expect(httpClientSpy.get)
          .toHaveBeenCalledWith(`${MTT_API_URL}/test_plans/${TEST_PLAN.id}`);
      expect(httpClientSpy.get).toHaveBeenCalledTimes(1);
      observable.subscribe((response) => {
        expect(response).toEqual(jasmine.objectContaining(TEST_PLAN));
      });
    });
  });

  describe('runTestPlan', () => {
    const TEST_PLAN = testUtil.newMockTestPlan();
    beforeEach(() => {
      httpClientSpy.post.and.returnValue(observableOf(null));
    });

    it('calls API and parses response correctly', () => {
      const observable = mttClient.runTestPlan(TEST_PLAN.id);
      expect(httpClientSpy.post)
          .toHaveBeenCalledWith(
              `${MTT_API_URL}/test_plans/${TEST_PLAN.id}/run`, null,
              jasmine.any(Object));
      expect(httpClientSpy.post).toHaveBeenCalledTimes(1);
      observable.subscribe((response) => {
        expect(response).toBeNull();
      });
    });
  });

  describe('getTestPlans', () => {
    const TEST_PLANS: TestPlanList = {
      test_plans: [
        testUtil.newMockTestPlan('test_plan_id_1', 'test_plan_name_1'),
        testUtil.newMockTestPlan('test_plan_id_2', 'test_plan_name_2')
      ]
    };

    beforeEach(() => {
      httpClientSpy.get.and.returnValue(observableOf(TEST_PLANS));
    });

    it('calls API and parses response correctly', () => {
      const observable = mttClient.getTestPlans();
      expect(httpClientSpy.get)
          .toHaveBeenCalledWith(`${MTT_API_URL}/test_plans`);
      expect(httpClientSpy.get).toHaveBeenCalledTimes(1);
      observable.subscribe((response) => {
        expect(response).toEqual(TEST_PLANS);
      });
    });
  });

  describe('deleteTestPlan', () => {
    const TEST_PLAN = testUtil.newMockTestPlan();
    beforeEach(() => {
      httpClientSpy.delete.and.returnValue(observableOf(null));
    });

    it('calls API and parses response correctly', () => {
      const observable = mttClient.deleteTestPlan(TEST_PLAN.id);
      expect(httpClientSpy.delete)
          .toHaveBeenCalledWith(
              `${MTT_API_URL}/test_plans/${TEST_PLAN.id}`, jasmine.any(Object));
      expect(httpClientSpy.delete).toHaveBeenCalledTimes(1);
      observable.subscribe((response) => {
        expect(response).toBeNull();
      });
    });
  });

  describe('createTestPlan', () => {
    const testPlan = testUtil.newMockTestPlan();
    beforeEach(() => {
      httpClientSpy.post.and.returnValue(observableOf(testPlan));
    });

    it('calls API and parses response correctly', () => {
      const observable = mttClient.createTestPlan(testPlan);
      expect(httpClientSpy.post)
          .toHaveBeenCalledWith(
              `${MTT_API_URL}/test_plans`, testPlan, jasmine.any(Object));
      expect(httpClientSpy.post).toHaveBeenCalledTimes(1);
      observable.subscribe((response) => {
        expect(response).toEqual(jasmine.objectContaining(testPlan));
      });
    });
  });

  describe('updateTestPlan', () => {
    const testPlan = testUtil.newMockTestPlan();
    beforeEach(() => {
      httpClientSpy.put.and.returnValue(observableOf(testPlan));
    });

    it('calls API and parses response correctly', () => {
      const observable = mttClient.updateTestPlan(testPlan.id, testPlan);
      expect(httpClientSpy.put)
          .toHaveBeenCalledWith(
              `${MTT_API_URL}/test_plans/${testPlan.id}`, testPlan,
              jasmine.any(Object));
      expect(httpClientSpy.put).toHaveBeenCalledTimes(1);
      observable.subscribe((response) => {
        expect(response).toEqual(jasmine.objectContaining(testPlan));
      });
    });
  });

  describe('getTestRun', () => {
    const testRun = testUtil.newMockTestRun(testUtil.newMockTest());

    beforeEach(() => {
      httpClientSpy.get.and.returnValue(observableOf(testRun));
    });

    it('calls API and parses response correctly', () => {
      const observable = mttClient.getTestRun(testRun.id);
      expect(httpClientSpy.get)
          .toHaveBeenCalledWith(`${MTT_API_URL}/test_runs/${testRun.id}`);
      expect(httpClientSpy.get).toHaveBeenCalledTimes(1);
      observable.subscribe((response) => {
        expect(response).toEqual(testRun);
      });
    });
  });

  describe('cancelTestRun', () => {
    const testRun = testUtil.newMockTestRun(testUtil.newMockTest());

    beforeEach(() => {
      httpClientSpy.post.and.returnValue(observableOf(null));
    });

    it('calls API and parses response correctly', () => {
      mttClient.cancelTestRun(testRun.id);
      expect(httpClientSpy.post)
          .toHaveBeenCalledWith(
              `${MTT_API_URL}/test_runs/${testRun.id}/cancel`, null,
              jasmine.any(Object));
      expect(httpClientSpy.post).toHaveBeenCalledTimes(1);
    });
  });

  describe('deleteTestRuns', () => {
    beforeEach(() => {
      httpClientSpy.delete.and.returnValue(observableOf(null));
    });

    it('calls API and parses response correctly', () => {
      mttClient.deleteTestRuns(['test_run_1', 'test_run_2']);
      const params = new HttpParams()
                         .append('test_run_ids', 'test_run_1')
                         .append('test_run_ids', 'test_run_2');
      expect(httpClientSpy.delete)
          .toHaveBeenCalledWith(
              `${MTT_API_URL}/test_runs`, jasmine.objectContaining({params}));
      expect(httpClientSpy.delete).toHaveBeenCalledTimes(1);
    });
  });

  describe('getTestRunOutput', () => {
    const test = testUtil.newMockTest();
    const testRun = testUtil.newMockTestRun(test);
    const testRunOutput = testUtil.newMockTestRunOutput();
    const attemptId = 'attemptId';
    const path = 'log/path';
    const offset = 3;

    beforeEach(() => {
      httpClientSpy.get.and.returnValue(observableOf(testRunOutput));
    });

    it('calls API correctly', () => {
      const observable =
          mttClient.getTestRunOutput(testRun.id, attemptId, path, offset);
      const params = new HttpParams()
                         .set('attempt_id', attemptId)
                         .set('path', path)
                         .set('offset', String(offset));

      expect(httpClientSpy.get)
          .toHaveBeenCalledWith(
              `${MTT_API_URL}/test_runs/${testRun.id}/output`, {params});
      expect(httpClientSpy.get).toHaveBeenCalledTimes(1);
      observable.subscribe((response) => {
        expect(response).toEqual(jasmine.objectContaining(testRunOutput));
      });
    });
  });

  describe('getFileCleanerSettings', () => {
    const FILE_CLEANER_SETTINGS = {
      policies: [testUtil.newMockFileCleanerPolicy()],
      configs: [testUtil.newMockFileCleanerConfig()],
    };

    beforeEach(() => {
      httpClientSpy.get.and.returnValue(observableOf(FILE_CLEANER_SETTINGS));
    });

    it('calls API and parses response correctly', () => {
      const observable = mttClient.getFileCleanerSettings();
      expect(httpClientSpy.get)
          .toHaveBeenCalledOnceWith(`${MTT_API_URL}/file_cleaner/settings`);
      observable.subscribe((response) => {
        expect(response).toEqual(FILE_CLEANER_SETTINGS);
      });
    });
  });

  describe('updateFileCleanerSettings', () => {
    const FILE_CLEANER_SETTINGS = {
      policies: [testUtil.newMockFileCleanerPolicy()],
      configs: [testUtil.newMockFileCleanerConfig()],
    };

    beforeEach(() => {
      httpClientSpy.put.and.returnValue(observableOf(FILE_CLEANER_SETTINGS));
    });

    it('calls API and parses response correctly', () => {
      const observable =
          mttClient.updateFileCleanerSettings(FILE_CLEANER_SETTINGS);
      expect(httpClientSpy.put)
          .toHaveBeenCalledOnceWith(
              `${MTT_API_URL}/file_cleaner/settings`, FILE_CLEANER_SETTINGS,
              jasmine.any(Object));
      observable.subscribe((response) => {
        expect(response).toEqual(FILE_CLEANER_SETTINGS);
      });
    });
  });

  describe('resetFileCleanerSettings', () => {
    it('calls API and parses response correctly', () => {
      mttClient.resetFileCleanerSettings();
      expect(httpClientSpy.delete)
          .toHaveBeenCalledOnceWith(
              `${MTT_API_URL}/file_cleaner/settings`, jasmine.any(Object));
    });
  });
});

describe('TestRunActionClient', () => {
  let http: jasmine.SpyObj<HttpClient>;
  let auth: jasmine.SpyObj<AuthService>;
  let client: TestRunActionClient;

  const action:
      TestRunAction = {id: 'id', name: 'name', hook_class_name: 'class_name'};

  beforeEach(() => {
    http = jasmine.createSpyObj<HttpClient>(
        'HttpClient', ['get', 'post', 'put', 'delete']);
    auth = jasmine.createSpyObj<AuthService>(
        'AuthService', ['getAuthorizationCode']);
    client = new TestRunActionClient(http, auth);
  });

  it('can list test run actions', () => {
    const actionList = {actions: [action]};
    http.get.and.returnValue(observableOf(actionList));
    client.list().subscribe(expectResponse([action]));
    expect(http.get).toHaveBeenCalledWith(TestRunActionClient.PATH);
    expect(http.get).toHaveBeenCalledTimes(1);
  });

  it('can get test run action', () => {
    http.get.and.returnValue(observableOf(action));
    client.get('id').subscribe(expectResponse(action));
    expect(http.get).toHaveBeenCalledWith(TestRunActionClient.PATH + '/id');
    expect(http.get).toHaveBeenCalledTimes(1);
  });

  it('can create test run action', () => {
    http.post.and.returnValue(observableOf(action));
    client.create(action).subscribe(expectResponse(action));
    expect(http.post).toHaveBeenCalledWith(
        TestRunActionClient.PATH, action, jasmine.any(Object));
    expect(http.post).toHaveBeenCalledTimes(1);
  });

  it('can update test run action', () => {
    http.put.and.returnValue(observableOf(action));
    client.update('id', action).subscribe(expectResponse(action));
    expect(http.put).toHaveBeenCalledWith(
        TestRunActionClient.PATH + '/id', action, jasmine.any(Object));
    expect(http.put).toHaveBeenCalledTimes(1);
  });

  it('can delete test run action', () => {
    http.delete.and.returnValue(observableOf());
    client.delete('id').subscribe();
    expect(http.delete)
        .toHaveBeenCalledWith(
            TestRunActionClient.PATH + '/id', jasmine.any(Object));
    expect(http.delete).toHaveBeenCalledTimes(1);
  });

  it('can authorize test run action', () => {
    const authInfo = {url: 'auth_url', is_manual: false};
    http.get.and.returnValue(observableOf(authInfo));
    auth.getAuthorizationCode.and.returnValue(observableOf('code'));
    http.post.and.returnValue(observableOf());

    client.authorize('id').subscribe();
    // Fetches authorization information
    const params = new HttpParams().set('redirect_uri', REDIRECT_URI);
    expect(http.get).toHaveBeenCalledWith(
        TestRunActionClient.PATH + '/id/auth', {params});
    expect(http.get).toHaveBeenCalledTimes(1);
    // Obtains authorization code from user
    expect(auth.getAuthorizationCode).toHaveBeenCalledWith(authInfo);
    expect(auth.getAuthorizationCode).toHaveBeenCalledTimes(1);
    // Sends authorization code
    expect(http.post).toHaveBeenCalledWith(
        TestRunActionClient.PATH + '/id/auth',
        {'redirect_uri': REDIRECT_URI, 'code': 'code'}, jasmine.any(Object));
    expect(http.post).toHaveBeenCalledTimes(1);
  });

  it('can authorize test run action with service account', done => {
    http.put.and.returnValue(observableOf({}));
    client.authorizeWithServiceAccount('id', new Blob(['key']))
        .subscribe(() => {
          // Uploads key content
          expect(http.put).toHaveBeenCalledWith(
              TestRunActionClient.PATH + '/id/auth', {value: 'key'},
              jasmine.any(Object));
          expect(http.put).toHaveBeenCalledTimes(1);
          done();
        });
  });

  it('can revoke test run action authorization', () => {
    http.delete.and.returnValue(observableOf());
    client.unauthorize('id').subscribe();
    expect(http.delete)
        .toHaveBeenCalledWith(
            TestRunActionClient.PATH + '/id/auth', jasmine.any(Object));
    expect(http.delete).toHaveBeenCalledTimes(1);
  });

  it('can execute test run actions', () => {
    const testRunActionRefs: TestRunActionRefList = {
      refs: [{
        action_id: 'action',
        options: [{name: 'option', value: 'value'}],
      }],
    };
    client.executeTestRunActions('test_run_id', testRunActionRefs);
    expect(http.post).toHaveBeenCalledWith(
        `${TestRunActionClient.PATH}/test_run_id`, testRunActionRefs,
        jasmine.any(Object));
    expect(http.post).toHaveBeenCalledTimes(1);
  });

  it('can list test run hooks', () => {
    client.listTestRunHooks();
    expect(http.get).toHaveBeenCalledWith(
        `${TestRunActionClient.PATH}/test_run_hooks`, jasmine.any(Object));
    expect(http.get).toHaveBeenCalledTimes(1);
  });
});

describe('NetdataClient', () => {
  let http: jasmine.SpyObj<HttpClient>;
  let client: NetdataClient;

  beforeEach(() => {
    http = jasmine.createSpyObj<HttpClient>('HttpClient', ['get']);
    client = new NetdataClient(http);
  });

  it('can get alarms', () => {
    const alarmList =
        testUtil.newMockNetdataAlarmList('hostname', 1, 'alarm1', '80%');
    http.get.and.returnValue(observableOf(alarmList));

    client.getAlarms(['alarm1', 'alarm2'], 'hostname')
        .subscribe(expectResponse(alarmList));

    const params = new HttpParams({
      fromObject: {
        'alarm_names': ['alarm1', 'alarm2'],
        'hostname': 'hostname',
      },
    });
    expect(http.get).toHaveBeenCalledWith(
        `${NetdataClient.PATH}/alarms`, {params});
    expect(http.get).toHaveBeenCalledTimes(1);
  });
});

describe('BuildClient', () => {
  let http: jasmine.SpyObj<HttpClient>;
  let client: BuildClient;

  const build: Build = {
    id: '123456',
    name: 'Foo',
    fingerprint: 'fingerprint',
    file_url: 'file:///root/file/path',
    size: 123123123,
    labels: [
      'MR',
      'UDC',
    ]
  };

  beforeEach(() => {
    http = jasmine.createSpyObj<HttpClient>(
        'HttpClient', ['get', 'post', 'put', 'delete']);
    client = new BuildClient(http);
  });

  it('can list builds', () => {
    const buildList: BuildList = {builds: [build]};
    http.get.and.returnValue(observableOf(buildList));
    client.list().subscribe(expectResponse(buildList));
    expect(http.get).toHaveBeenCalledWith(BuildClient.PATH);
    expect(http.get).toHaveBeenCalledTimes(1);
  });

  it('can get build', () => {
    http.get.and.returnValue(observableOf(build));
    client.get('id').subscribe(expectResponse(build));
    expect(http.get).toHaveBeenCalledWith(BuildClient.PATH + '/id');
    expect(http.get).toHaveBeenCalledTimes(1);
  });

  it('can create build', () => {
    http.post.and.returnValue(observableOf(build));
    client.create(build).subscribe(expectResponse(build));
    expect(http.post).toHaveBeenCalledWith(
        BuildClient.PATH, build, jasmine.any(Object));
    expect(http.post).toHaveBeenCalledTimes(1);
  });

  it('can update build', () => {
    http.put.and.returnValue(observableOf(build));
    client.update('id', build).subscribe(expectResponse(build));
    expect(http.put).toHaveBeenCalledWith(
        BuildClient.PATH + '/id', build, jasmine.any(Object));
    expect(http.put).toHaveBeenCalledTimes(1);
  });

  it('can delete builds', () => {
    http.delete.and.returnValue(observableOf());
    client.delete(['id_1', 'id_2']).subscribe();
    const params = new HttpParams()
                       .append('build_ids', 'id_1')
                       .append('build_ids', 'id_2');
    expect(http.delete)
        .toHaveBeenCalledWith(
            BuildClient.PATH, jasmine.objectContaining({params}));
    expect(http.delete).toHaveBeenCalledTimes(1);
  });

  it('can delect xts requirements', () => {
    const request: XtsRequirementsDetectionRequest = {
      device_spec: '',
      test_resource_objs: []
    };
    http.post.and.returnValue(observableOf(build));
    client.detect(build.id!, request).subscribe();
    expect(http.post).toHaveBeenCalledWith(
        `${BuildClient.PATH}/${build.id}/detect`, request, jasmine.any(Object));
    expect(http.post).toHaveBeenCalledTimes(1);
  });
});

/** Convenience method to verify the response in a subscription. */
function expectResponse<T>(expected: T): (actual: T) => void {
  return actual => {
    expect(actual).toEqual(expected);
  };
}
