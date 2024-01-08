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
import {Injectable} from '@angular/core';
import {EMPTY, from, Observable} from 'rxjs';
import {map, switchMap} from 'rxjs/operators';

import {AnalyticsContext} from './analytics_service';
import {AuthService, REDIRECT_URI} from './auth_service';
import {readBlobAsText} from './file_service';
import * as model from './mtt_models';

/** URL for MTT API methods */
export const MTT_API_URL = '/_ah/api/mtt/v1';

/** Client for MTT API access */
@Injectable({
  providedIn: 'root',
})
export class MttClient {
  readonly configSets: ConfigSetClient;
  readonly testRunActions: TestRunActionClient;
  readonly testResults: TestResultClient;
  readonly netdata: NetdataClient;
  readonly builds: BuildClient;

  constructor(
      private readonly http: HttpClient, private readonly auth: AuthService) {
    // TODO: Reorganize MttClient methods
    this.configSets = new ConfigSetClient(http);
    this.testRunActions = new TestRunActionClient(http, auth);
    this.testResults = new TestResultClient(http);
    this.netdata = new NetdataClient(http);
    this.builds = new BuildClient(http);
  }

  /**
   * Authorizes a build channel using an authorization code.
   * @param buildChannelId: build channel to authorize
   */
  authorizeBuildChannel(buildChannelId: string): Observable<void> {
    return this.getBuildChannelAuthorizationInfo(buildChannelId)
        .pipe(switchMap(authInfo => this.auth.getAuthorizationCode(authInfo)))
        .pipe(switchMap(code => {
          if (!code) {
            return EMPTY;
          }
          return this.sendBuildChannelAuthorizationCode(buildChannelId, code);
        }));
  }

  /** Sends build channel authorization code to complete flow. */
  private sendBuildChannelAuthorizationCode(
      buildChannelId: string, code: string): Observable<void> {
    const context = AnalyticsContext.create('build_channels', 'authorize');
    return this.http.post<void>(
        `${MTT_API_URL}/build_channels/${
            encodeURIComponent(buildChannelId)}/auth`,
        {'redirect_uri': REDIRECT_URI, 'code': code}, {context});
  }

  /** Fetches a build channel's authorization information to start flow. */
  private getBuildChannelAuthorizationInfo(buildChannelId: string):
      Observable<model.AuthorizationInfo> {
    const params = new HttpParams().set('redirect_uri', REDIRECT_URI);
    return this.http.get<model.AuthorizationInfo>(
        `${MTT_API_URL}/build_channels/${
            encodeURIComponent(buildChannelId)}/auth`,
        {params});
  }

  /** Authorizes a build channel with a service account JSON key. */
  authorizeBuildChannelWithServiceAccount(buildChannelId: string, key: Blob):
      Observable<void> {
    return from(readBlobAsText(key)).pipe(switchMap(data => {
      const context = AnalyticsContext.create('build_channels', 'authorize');
      return this.http.put<void>(
          `${MTT_API_URL}/build_channels/${
              encodeURIComponent(buildChannelId)}/auth`,
          {value: data}, {context});
    }));
  }

  /** Revokes a build channel's authorization. */
  unauthorizeBuildChannel(buildChannelId: string): Observable<void> {
    const context = AnalyticsContext.create('build_channels', 'unauthorize');
    return this.http.delete<void>(
        `${MTT_API_URL}/build_channels/${
            encodeURIComponent(buildChannelId)}/auth`,
        {context});
  }

  lookupBuildItem(url: string): Observable<model.BuildItem> {
    const params = new HttpParams().set('url', url);
    return this.http.get<model.BuildItem>(
        `${MTT_API_URL}/build_channels/build_item_lookup`, {params});
  }

  listBuildItems(id: string, path: string, pageToken?: string):
      Observable<model.BuildItemList> {
    let params = new HttpParams().set('path', path);
    if (pageToken) {
      params = params.set('page_token', pageToken);
    }
    return this.http.get<model.BuildItemList>(
        `${MTT_API_URL}/build_channels/${encodeURIComponent(id)}/build_items`,
        {params});
  }

  deleteBuildItem(id: string, path: string) {
    const context =
        AnalyticsContext.create('build_channels', 'delete_build_item');
    const params = new HttpParams().set('path', path);
    return this.http.delete(
        `${MTT_API_URL}/build_channels/${encodeURIComponent(id)}/build_items`,
        {context, params});
  }

  getBuildChannelProviders(): Observable<model.BuildChannelProviderList> {
    return this.http.get<model.BuildChannelProviderList>(
        `${MTT_API_URL}/build_channel_providers`);
  }

  getBuildChannelProvider(id: string) {
    return this.http.get(
        `${MTT_API_URL}/build_channel_providers/${encodeURIComponent(id)}`);
  }

  createBuildChannel(buildChannelConfig: model.BuildChannelConfig) {
    const context = AnalyticsContext.create('build_channels', 'create');
    return this.http.post(
        `${MTT_API_URL}/build_channels`, buildChannelConfig, {context});
  }

  getBuildChannel(id: string) {
    return this.http.get<model.BuildChannelConfig>(
        `${MTT_API_URL}/build_channels/${encodeURIComponent(id)}`);
  }

  getBuildChannels(): Observable<model.BuildChannelList> {
    return this.http.get<model.BuildChannelList>(
        `${MTT_API_URL}/build_channels`);
  }

  updateBuildChannel(
      buildChannelId: string, buildChannelConfig: model.BuildChannelConfig) {
    const context = AnalyticsContext.create('build_channels', 'update');
    return this.http.put(
        `${MTT_API_URL}/build_channels/${encodeURIComponent(buildChannelId)}`,
        buildChannelConfig, {context});
  }

  deleteBuildChannel(id: string) {
    const context = AnalyticsContext.create('build_channels', 'delete');
    return this.http.delete(
        `${MTT_API_URL}/build_channels/${encodeURIComponent(id)}`, {context});
  }

  getConfigSetBuildChannels(): Observable<model.BuildChannelList> {
    return this.http.get(`${MTT_API_URL}/config_sets/build_channels`);
  }

  getConfigSetInfos(
      includeRemote = false, statuses: model.ConfigSetStatus[] = []):
      Observable<model.ConfigSetInfoList> {
    const params = new HttpParams({
      fromObject: {
        'include_remote': `${includeRemote}`,
        'statuses': statuses,
      }
    });
    return this.http.get<model.ConfigSetInfoList>(
        `${MTT_API_URL}/config_sets`, {params});
  }

  importConfigSet(url = '', content = ''): Observable<model.ConfigSetInfo> {
    const context = AnalyticsContext.create('config_sets', 'import');
    if (!url) {
      url = 'local';
    }
    return this.http.post<model.ConfigSetInfo>(
        `${MTT_API_URL}/config_sets/import/${encodeURIComponent(url)}`,
        {'content': content}, {context});
  }

  deleteConfigSet(url: string) {
    const context = AnalyticsContext.create('config_sets', 'delete');
    return this.http.delete(
        `${MTT_API_URL}/config_sets/${encodeURIComponent(url)}`, {context});
  }

  getDeviceAction(id: string): Observable<model.DeviceAction> {
    return this.http.get<model.DeviceAction>(
        `${MTT_API_URL}/device_actions/${encodeURIComponent(id)}`);
  }

  getDeviceActionList(): Observable<model.DeviceActionList> {
    return this.http.get<model.DeviceActionList>(
        `${MTT_API_URL}/device_actions`);
  }

  createDeviceAction(deviceAction: model.DeviceAction) {
    const context = AnalyticsContext.create('device_actions', 'create');
    return this.http.post(
        `${MTT_API_URL}/device_actions`, deviceAction, {context});
  }

  updateDeviceAction(id: string, deviceAction: model.DeviceAction) {
    const context = AnalyticsContext.create('device_actions', 'update');
    return this.http.put(
        `${MTT_API_URL}/device_actions/${encodeURIComponent(id)}`, deviceAction,
        {context});
  }

  deleteDeviceAction(id: string) {
    const context = AnalyticsContext.create('device_actions', 'delete');
    return this.http.delete(
        `${MTT_API_URL}/device_actions/${encodeURIComponent(id)}`, {context});
  }

  createNewTestRunRequest(newtestRun: model.NewTestRunRequest):
      Observable<model.TestRun> {
    const context = AnalyticsContext.create('test_runs', 'create');
    return this.http.post<model.TestRun>(
        `${MTT_API_URL}/test_runs`, newtestRun, {context});
  }

  getNodeConfig(): Observable<model.NodeConfig> {
    return this.http.get<model.NodeConfig>(`${MTT_API_URL}/node_config`);
  }

  updateNodeConfig(nodeConfig: model.NodeConfig) {
    const context = AnalyticsContext.create('node_config', 'update');
    return this.http.put(`${MTT_API_URL}/node_config`, nodeConfig, {context});
  }

  exportNodeConfig(): Observable<model.SimpleMessage> {
    const context = AnalyticsContext.create('node_config', 'export');
    return this.http.get<model.SimpleMessage>(
        `${MTT_API_URL}/node_config/export`, {context});
  }

  importNodeConfig(value: string): Observable<void> {
    const context = AnalyticsContext.create('node_config', 'import');
    return this.http.post<void>(
        `${MTT_API_URL}/node_config/import`, {'value': value}, {context});
  }

  getPrivateNodeConfig(): Observable<model.PrivateNodeConfig> {
    return this.http.get<model.PrivateNodeConfig>(
        `${MTT_API_URL}/private_node_config`);
  }

  updatePrivateNodeConfig(privateNodeConfig: model.PrivateNodeConfig) {
    const context = AnalyticsContext.create('private_node_config', 'update');
    return this.http.put(
        `${MTT_API_URL}/private_node_config`, privateNodeConfig, {context});
  }

  setDefaultServiceAccount(key: Blob): Observable<void> {
    return from(readBlobAsText(key)).pipe(switchMap(data => {
      const context = AnalyticsContext.create(
          'private_node_config', 'set_default_service_account');
      return this.http.put<void>(
          `${MTT_API_URL}/private_node_config/default_service_account`,
          {value: data}, {context});
    }));
  }

  removeDefaultServiceAccount() {
    const context = AnalyticsContext.create(
        'private_node_config', 'remove_default_service_account');
    return this.http.delete(
        `${MTT_API_URL}/private_node_config/default_service_account`,
        {context});
  }

  createTest(test: model.Test) {
    const context = AnalyticsContext.create('tests', 'create');
    return this.http.post(`${MTT_API_URL}/tests`, test, {context});
  }

  getTest(id: string): Observable<model.Test> {
    return this.http.get<model.Test>(
        `${MTT_API_URL}/tests/${encodeURIComponent(id)}`);
  }

  getTests(): Observable<model.TestList> {
    return this.http.get<model.TestList>(`${MTT_API_URL}/tests`);
  }

  updateTest(testId: string, test: model.Test) {
    const context = AnalyticsContext.create('tests', 'update');
    return this.http.put(
        `${MTT_API_URL}/tests/${encodeURIComponent(testId)}`, test, {context});
  }

  deleteTest(id: string) {
    const context = AnalyticsContext.create('tests', 'delete');
    return this.http.delete(
        `${MTT_API_URL}/tests/${encodeURIComponent(id)}`, {context});
  }

  createTestPlan(testPlan: model.TestPlan) {
    const context = AnalyticsContext.create('test_plans', 'create');
    return this.http.post<model.TestPlan>(
        `${MTT_API_URL}/test_plans`, testPlan, {context});
  }

  updateTestPlan(testPlanId: string, testPlan: model.TestPlan) {
    const context = AnalyticsContext.create('test_plans', 'update');
    return this.http.put<model.TestPlan>(
        `${MTT_API_URL}/test_plans/${encodeURIComponent(testPlanId)}`, testPlan,
        {context});
  }

  getTestPlan(id: string): Observable<model.TestPlan> {
    return this.http.get<model.TestPlan>(
        `${MTT_API_URL}/test_plans/${encodeURIComponent(id)}`);
  }

  getTestPlans(): Observable<model.TestPlanList> {
    return this.http.get<model.TestPlanList>(`${MTT_API_URL}/test_plans`);
  }

  runTestPlan(id: string) {
    const context = AnalyticsContext.create('test_plans', 'run');
    return this.http.post(
        `${MTT_API_URL}/test_plans/${encodeURIComponent(id)}/run`, null,
        {context});
  }

  deleteTestPlan(id: string) {
    const context = AnalyticsContext.create('test_plans', 'delete');
    return this.http.delete(
        `${MTT_API_URL}/test_plans/${encodeURIComponent(id)}`, {context});
  }

  getTestRun(id: string): Observable<model.TestRun> {
    return this.http.get<model.TestRun>(
        `${MTT_API_URL}/test_runs/${encodeURIComponent(id)}`);
  }

  cancelTestRun(id: string) {
    const context = AnalyticsContext.create('test_runs', 'cancel');
    return this.http.post(
        `${MTT_API_URL}/test_runs/${encodeURIComponent(id)}/cancel`, null,
        {context});
  }

  deleteTestRuns(ids: string[]) {
    const context = AnalyticsContext.create('test_runs', 'delete');
    const params = new HttpParams().appendAll({'test_run_ids': ids});
    return this.http.delete(`${MTT_API_URL}/test_runs`, {context, params});
  }

  getTestRuns(
      maxResults?: number, pageToken?: string, backwards = false,
      filterQueries: string[] = [],
      state: model.TestRunState[] = []): Observable<model.TestRunSummaryList> {
    const params = new HttpParams({
      fromObject: {
        'max_results': maxResults ? String(maxResults) : '',
        'page_token': pageToken || '',
        'backwards': String(backwards),
        'filter_query': filterQueries,
        'state': state,
      }
    });

    return this.http.get<model.TestRunSummaryList>(
        `${MTT_API_URL}/test_runs`, {params});
  }

  getReruns(id: string) {
    const params = new HttpParams({fromObject: {'prev_test_run_id': id}});
    return this.http.get<model.TestRunSummaryList>(
        `${MTT_API_URL}/test_runs`, {params});
  }

  getTestRunOutput(
      testRunId: string, attemptId: string, path: string,
      offset?: number): Observable<model.TestRunOutput> {
    let params =
        new HttpParams().set('attempt_id', attemptId).set('path', path);
    if (typeof offset !== 'undefined') {
      params = params.set('offset', String(offset));
    }

    return this.http.get<model.TestRunOutput>(
        `${MTT_API_URL}/test_runs/${encodeURIComponent(testRunId)}/output`,
        {params});
  }

  getFileCleanerSettings() {
    return this.http.get<model.FileCleanerSettings>(
        `${MTT_API_URL}/file_cleaner/settings`);
  }

  updateFileCleanerSettings(settings: model.FileCleanerSettings) {
    const context = AnalyticsContext.create('file_cleaner', 'update');
    return this.http.put(
        `${MTT_API_URL}/file_cleaner/settings`, settings, {context});
  }

  resetFileCleanerSettings() {
    const context = AnalyticsContext.create('file_cleaner', 'reset');
    return this.http.delete(`${MTT_API_URL}/file_cleaner/settings`, {context});
  }
}

/** Provides access to the config set API. */
export class ConfigSetClient {
  static readonly PATH = `${MTT_API_URL}/config_sets`;

  constructor(private readonly http: HttpClient) {}

  getLatestVersion(importedInfo: model.ConfigSetInfo):
      Observable<model.ConfigSetInfo> {
    return this.http.post<model.ConfigSetInfo>(
        `${ConfigSetClient.PATH}/latest_version`, importedInfo);
  }
}

/** Provides access to the test run action API. */
export class TestRunActionClient {
  /** Backend path which serves test run action data. */
  static readonly PATH = `${MTT_API_URL}/test_run_actions`;

  constructor(
      private readonly http: HttpClient, private readonly auth: AuthService) {}

  /** Lists all test run actions. */
  list(): Observable<model.TestRunAction[]> {
    return this.http.get<model.TestRunActionList>(TestRunActionClient.PATH)
        .pipe(map(result => result.actions || []));
  }

  /** Returns a test run action using its ID. */
  get(id: string): Observable<model.TestRunAction> {
    return this.http.get<model.TestRunAction>(
        `${TestRunActionClient.PATH}/${encodeURIComponent(id)}`);
  }

  /** Creates a new test run action. */
  create(data: model.TestRunAction): Observable<model.TestRunAction> {
    const context = AnalyticsContext.create('test_run_actions', 'create');
    return this.http.post<model.TestRunAction>(
        TestRunActionClient.PATH, data, {context});
  }

  /** Updates an existing test run action. */
  update(id: string, data: model.TestRunAction):
      Observable<model.TestRunAction> {
    const context = AnalyticsContext.create('test_run_actions', 'update');
    return this.http.put<model.TestRunAction>(
        `${TestRunActionClient.PATH}/${encodeURIComponent(id)}`, data,
        {context});
  }

  /** Deletes a test run action. */
  delete(id: string): Observable<void> {
    const context = AnalyticsContext.create('test_run_actions', 'delete');
    return this.http.delete<void>(
        `${TestRunActionClient.PATH}/${encodeURIComponent(id)}`, {context});
  }

  /** Authorizes a test run action. */
  authorize(id: string): Observable<void> {
    return this.getAuthorizationInfo(id)
        .pipe(switchMap(authInfo => this.auth.getAuthorizationCode(authInfo)))
        .pipe(switchMap(
            code => code ? this.sendAuthorizationCode(id, code) : EMPTY));
  }

  /** Authorizes a test run action with a service account JSON key. */
  authorizeWithServiceAccount(id: string, key: Blob): Observable<void> {
    return from(readBlobAsText(key)).pipe(switchMap(data => {
      const context = AnalyticsContext.create('test_run_actions', 'authorize');
      return this.http.put<void>(
          `${TestRunActionClient.PATH}/${encodeURIComponent(id)}/auth`,
          {value: data}, {context});
    }));
  }

  /** Revokes a test run action's authorization. */
  unauthorize(id: string): Observable<void> {
    const context = AnalyticsContext.create('test_run_actions', 'unauthorize');
    return this.http.delete<void>(
        `${TestRunActionClient.PATH}/${encodeURIComponent(id)}/auth`,
        {context});
  }

  /** Executes test run actions for a test run with given references. */
  executeTestRunActions(
      testRunId: string, testRunActionRefs: model.TestRunActionRefList) {
    const context = AnalyticsContext.create('test_run_actions', 'execute');
    return this.http.post(
        `${TestRunActionClient.PATH}/${encodeURIComponent(testRunId)}`,
        testRunActionRefs, {context});
  }

  /** Lists all registered test run hooks. */
  listTestRunHooks(): Observable<model.TestRunHookList> {
    const context =
        AnalyticsContext.create('test_run_actions', 'list_test_run_hooks');
    return this.http.get<model.TestRunHookList>(
        `${TestRunActionClient.PATH}/test_run_hooks`, {context});
  }

  // Fetches authorization information to start authorization flow.
  private getAuthorizationInfo(id: string):
      Observable<model.AuthorizationInfo> {
    const params = new HttpParams().set('redirect_uri', REDIRECT_URI);
    return this.http.get<model.AuthorizationInfo>(
        `${TestRunActionClient.PATH}/${encodeURIComponent(id)}/auth`, {params});
  }

  // Sends authorization code to complete authorization flow.
  private sendAuthorizationCode(id: string, code: string): Observable<void> {
    const context = AnalyticsContext.create('test_run_actions', 'authorize');
    return this.http.post<void>(
        `${TestRunActionClient.PATH}/${encodeURIComponent(id)}/auth`,
        {'redirect_uri': REDIRECT_URI, 'code': code}, {context});
  }
}

/** Provides access to the test results API. */
export class TestResultClient {
  /** Backend path which serves test run action data. */
  static readonly PATH = `${MTT_API_URL}/test_results`;
  static readonly PAGE_SIZE = 20;

  constructor(private readonly http: HttpClient) {}

  /** Lists all modules. */
  listModules(testRunId: string): Observable<model.TestModuleResultList> {
    const params = new HttpParams().set('test_run_id', testRunId);
    return this.http.get<model.TestModuleResultList>(
        `${TestResultClient.PATH}/modules`, {params});
  }

  listTestCases(
      moduleId: string, pageToken?: string,
      pageSize = TestResultClient.PAGE_SIZE):
      Observable<model.TestCaseResultList> {
    let params = new HttpParams();
    params = params.set('max_results', pageSize);
    params = params.set('page_token', pageToken || '');

    // TODO: Add name and status filtering

    return this.http.get<model.TestCaseResultList>(
        `${TestResultClient.PATH}/modules/${
            encodeURIComponent(moduleId)}/test_cases`,
        {params});
  }
}

/** Provides access to the Netdata API. */
export class NetdataClient {
  /** Backend path which serves Netdata data. */
  static readonly PATH = `${MTT_API_URL}/netdata`;

  constructor(private readonly http: HttpClient) {}

  /** Gets raised alarms. */
  getAlarms(alarmNames: string[], hostname: string):
      Observable<model.NetdataAlarmList> {
    const params = new HttpParams({
      fromObject: {
        'alarm_names': alarmNames,
        hostname,
      },
    });
    return this.http.get(`${NetdataClient.PATH}/alarms`, {params});
  }
}

/** Provides access to the Build API. */
export class BuildClient {
  /** Backend path which serves Build data. */
  static readonly PATH = `${MTT_API_URL}/builds`;

  constructor(private readonly http: HttpClient) {}

  /** Lists all builds. */
  list(): Observable<model.BuildList> {
    return this.http.get<model.BuildList>(BuildClient.PATH);
  }

  /** Returns a build using its ID. */
  get(id: string): Observable<model.Build> {
    return this.http.get<model.Build>(
        `${BuildClient.PATH}/${encodeURIComponent(id)}`);
  }

  /** Creates a new build. */
  create(data: model.Build): Observable<model.Build> {
    const context = AnalyticsContext.create('builds', 'create');
    return this.http.post<model.Build>(BuildClient.PATH, data, {context});
  }

  /** Updates an existing build. */
  update(id: string, data: model.Build): Observable<model.Build> {
    const context = AnalyticsContext.create('builds', 'update');
    return this.http.put<model.Build>(
        `${BuildClient.PATH}/${encodeURIComponent(id)}`, data, {context});
  }

  /** Deletes a list of builds. */
  delete(ids: string[]): Observable<void> {
    const context = AnalyticsContext.create('builds', 'delete');
    const params = new HttpParams().appendAll({'build_ids': ids});
    return this.http.delete<void>(BuildClient.PATH, {context, params});
  }

  detect(
      buildId: string,
      xtsRequirementsDetectionRequest: model.XtsRequirementsDetectionRequest):
      Observable<model.Build> {
    const context = AnalyticsContext.create('builds', 'detect');
    return this.http.post<model.Build>(
        `${MTT_API_URL}/builds/${encodeURIComponent(buildId)}/detect`,
        xtsRequirementsDetectionRequest, {context});
  }
}
