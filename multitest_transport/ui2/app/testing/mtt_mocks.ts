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

import * as moment from 'moment';

import * as mttModels from '../services/mtt_models';
import * as tfcModels from '../services/tfc_models';

// CONSTANTS;
const ATTEMPT_ID = 'attemptid789';
const BUILD_ID = 'build_id';
const BUILD_NAME = 'build_name';
const BUILD_URL = 'file:///build/path';
const BUILD_CHANNEL_ID = 'test_build_channel_id';
const BUILD_CHANNEL_NAME = 'test_build_channel_name';
const BUILD_CHANNEL_PROVIDER_NAME = 'Partner Android Build';
const BUILD_ITEM_NAME = 'test_build_item_name';
const CLUSTER = 'cluster1';
const COMMAND_ID = 'commandid456';
const COMMAND_STATE = tfcModels.CommandState.RUNNING;
const CONFIG_SET_URL = 'mtt://android-mtt.appspot.com/google_cloud_storage/url';
const CONFIG_SET_NAME = 'Test Config Set';
const CONFIG_SET_HASH = 'someconfigsethash12345';
const DATE = new Date().toISOString();
const DATE_FUTURE = addTime(DATE, 0, 5, 0);  // 5 minutes later
const DEVICE_ACTION_ID = 'reset';
const DEVICE_ACTION_NAME = 'Factory Reset';
const FAILED_TEST_COUNT = 13;
const HOSTNAME = 'hostname';
const LABEL1 = 'label1';
const LABEL2 = 'label2';
const OPTION_DEF_NAME = 'test_name';
const PREVIOUS_TEST_RUN_ID = '12345678';
const REQUEST_ID = 'requestid123';
const REQUEST_STATE = tfcModels.RequestState.RUNNING;
const RUN_TARGET_LIST = ['target1', 'target2'];
const RUN_TARGET_STRING = RUN_TARGET_LIST.join(';');
const TARGET_PREPARER_CLASS_NAME = 'test_class_name';
const TEST_COMMAND = 'test_command';
const TEST_GROUP_STATUS_NAME = 'testgroupstatusname';
const TEST_ID = 'testid123';
const TEST_NAME = 'test456';
const TEST_RESOURCE_DEF_NAME = 'testname';
const TEST_RESOURCE_DEF_DEFAULT_DOWNLOAD_URL = 'url';
const TEST_RESOURCE_TYPE = mttModels.TestResourceType.TEST_PACKAGE;
const TEST_RETRY_COMMAND = 'test_retry_command';
const TEST_RUN_ID = 'id123';
const TEST_RUN_OUTPUT_LINES = [
  'Invocation finished in 100s. PASSED: 42, FAILED: 13, MODULES: 2 of 2\n',
  'Saved log to /tmp/tradefed_global_log_123456789.txt\n',
  '06-12 10:38:07 I/CommandScheduler: All done\n'
];
const TEST_RUN_STATE = mttModels.TestRunState.RUNNING;
const TEST_PACKAGE_NAME = 'CTS 8.1';
const TEST_PACKAGE_VERSION = 'r11';
const TEST_PLAN_ID = 'test_plan_id';
const TEST_PLAN_NAME = 'test_plan_name';
const TOTAL_TEST_COUNT = 42;

/*******************************************
 * Functions to create mock MTT API objects
 *******************************************/

/** Creates a new mock CredentialsInfo object */
export function newMockCredentialsInfo(email = 'credentials_email@google.com') {
  return {
    email,
  };
}

/** Create a new Build Channel */
export function newMockBuildChannel(
    id = BUILD_CHANNEL_ID, name = BUILD_CHANNEL_NAME) {
  return {
    id,
    name,
    provider_name: 'Local File Store',
    auth_state: mttModels.AuthorizationState.NOT_APPLICABLE,
    auth_methods: [],
    build_item_path_type: mttModels.BuildItemPathType.DIRECTORY_FILE,
  };
}

/** Create a new Build Channel Config */
export function newMockBuildChannelConfig(
    id = BUILD_CHANNEL_ID, name = BUILD_CHANNEL_NAME,
    providerName = BUILD_CHANNEL_PROVIDER_NAME) {
  return {
    id,
    name,
    provider_name: providerName,
    options: [{name: 'account_id', value: '3333333'}]
  };
}

/** Create a new Build Channel Provider */
export function newMockBuildChannelProvider(
    name = BUILD_CHANNEL_NAME, optionDefs?: mttModels.OptionDef[]) {
  if (optionDefs === undefined) {
    return {name};
  }
  return {name, option_defs: optionDefs};
}

/** Create a new Build Channel Provider List */
export function newMockBuildChannelProviderList() {
  return [
    newMockBuildChannelProvider(
        'Test Storage', [newMockOptionDef('test_name')]),
    newMockBuildChannelProvider(
        'Google Cloud Storage', [newMockOptionDef('bucket_name')]),
    newMockBuildChannelProvider('Android'),
    newMockBuildChannelProvider('Local File Store'),
    newMockBuildChannelProvider(
        'Partner Android Build', [newMockOptionDef('account_id')])
  ];
}

/** Create a mock buildItem */
export function newMockBuildItem(name = BUILD_ITEM_NAME) {
  return {
    name,
    path: 'build/item/path',
    is_file: true,
    size: 0,
    timestamp: DATE,
    description: 'this is description'
  };
}

/** Create a mock buildItemList */
export function newMockBuildItemList() {
  return {
    build_items:
        [newMockBuildItem('a'), newMockBuildItem('b'), newMockBuildItem('c')],
    next_page_token: 'fake_token'
  };
}

/** Create a mock ConfigSetInfo */
export function newMockConfigSetInfo(
    url = CONFIG_SET_URL, name = CONFIG_SET_NAME, hash = CONFIG_SET_HASH,
    status = mttModels.ConfigSetStatus.IMPORTED) {
  return {url, name, hash, status};
}

/** Create a mock ConfigSetInfo that has been imported */
export function newMockImportedConfigSetInfo() {
  return newMockConfigSetInfo(
      'mtt:///imported/config/set/info', 'Imported Config Set', 'importedhash',
      mttModels.ConfigSetStatus.IMPORTED);
}


/** Create a mock ConfigSetInfo that has not been imported */
export function newMockNotImportedConfigSetInfo() {
  return newMockConfigSetInfo(
      'mtt:///not/imported/config/set/info', 'Not-imported Config Set',
      'notimportedhash', mttModels.ConfigSetStatus.NOT_IMPORTED);
}

/** Creates a new Device Action */
export function newMockDeviceAction(
    id = DEVICE_ACTION_ID, name = DEVICE_ACTION_NAME): mttModels.DeviceAction {
  return {id, name};
}

/** Create a list of Device Action */
export function newMockDeviceActionList() {
  return [
    newMockDeviceAction('id1', 'name1'),
    newMockDeviceAction('id2', 'name2'),
    newMockDeviceAction('id3', 'name3'),
  ];
}

/** Creates a new mock invocation status object */
export function newMockInvocationStatus() {
  return {
    test_group_statuses: [
      newMockTestGroupStatus('Passing Module', 3, 0, true, 50),
      newMockTestGroupStatus('Failing Module', 29, 13, true, 12345, 'msg 2'),
    ]
  };
}

/** Creates a new NameMultiValuePair object */
export function newMockNameMultiValuePair(name: string) {
  return {
    name,
    values: ['a', 'b', 'c'],
  };
}

/** Creates a list of NameMultiValuePair object */
export function newMockNameMultiValuePairList() {
  return [
    newMockNameMultiValuePair('testa'),
    newMockNameMultiValuePair('testb'),
    newMockNameMultiValuePair('testc'),
    newMockNameMultiValuePair('testd'),
  ];
}

/** Creates a Name Value Pair object */
export function newMockNameValuePair(name: string, value?: string) {
  return {name, value};
}

/** Creates a list of Name Value Pair object */
export function newMockNameValuePairList() {
  return [
    newMockNameValuePair('pair1', 'value1'),
    newMockNameValuePair('pair2', 'value2'),
    newMockNameValuePair('pair3', 'value3'),
  ];
}

/** Create a new Test Run Request */
export function newMockNewTestRunRequest() {
  return {
    prev_test_run_id: PREVIOUS_TEST_RUN_ID,
    test_run_config: newMockTestRunConfig(TEST_ID),
  };
}

/** Create a mock a node config object */
export function newMockNodeConfig() {
  return {};
}

/** Create new build channel provider option definition */
export function newMockOptionDef(name = OPTION_DEF_NAME) {
  return {name, value_type: 'str', choices: [], default: ''};
}

/** Creates a new Test */
export function newMockTest(
    id = TEST_ID, name = TEST_NAME, command = TEST_COMMAND,
    retryCommand = TEST_RETRY_COMMAND) {
  return {
    id,
    name,
    command,
    retry_command_line: retryCommand,
    default_test_run_parameters: {
      max_retry_on_test_failures: 1,
      invocation_timeout_seconds: 0,
      output_idle_timeout_seconds: 1000,
    },
  };
}

/** Creates a new mock test group status */
export function newMockTestGroupStatus(
    name = TEST_GROUP_STATUS_NAME, failedTestCount?: number,
    passedTestCount?: number, isCompleted?: boolean, elapsedTime?: number,
    failureMessage?: string) {
  return {
    name,
    failed_test_count: failedTestCount,
    passed_test_count: passedTestCount,
    is_completed: isCompleted,
    elapsed_time: elapsedTime,
    failure_message: failureMessage,
  };
}

/** Creates a new Test Package Info object */
export function newMockTestPackageInfo(
    name = TEST_PACKAGE_NAME, version = TEST_PACKAGE_VERSION) {
  return {name, version};
}

/** Creates a new Test Plan */
export function newMockTestPlan(id = TEST_PLAN_ID, name = TEST_PLAN_NAME) {
  return {id, name, test_run_sequences: [], labels: [], cron_exp: '* * * * *'};
}

/** Creates a list of new test resource def object */
export function newMockTestResourceDefs(): mttModels.TestResourceDef[] {
  return [
    newMockTestResourceDef(
        'name1', 'url1', mttModels.TestResourceType.DEVICE_IMAGE),
    newMockTestResourceDef(
        'name2', 'url2', mttModels.TestResourceType.UNKNOWN, true, 'dir2',
        ['file2']),
  ];
}

/** Creates a new test resource def object */
export function newMockTestResourceDef(
    name = TEST_RESOURCE_DEF_NAME,
    defaultDownloadUrl = TEST_RESOURCE_DEF_DEFAULT_DOWNLOAD_URL,
    testResourceType: mttModels.TestResourceType, decompress?: boolean,
    decompressDir?: string,
    decompressFiles?: string[]): mttModels.TestResourceDef {
  return {
    name,
    default_download_url: defaultDownloadUrl,
    test_resource_type: testResourceType,
    decompress,
    decompress_dir: decompressDir,
    params: {decompress_files: decompressFiles},
  };
}

/** Creates a new mock test resource object */
export function newMockTestResourceObj(
    name = TEST_RESOURCE_DEF_NAME, url = TEST_RESOURCE_DEF_DEFAULT_DOWNLOAD_URL,
    cacheUrl = TEST_RESOURCE_DEF_DEFAULT_DOWNLOAD_URL,
    testResourceType = TEST_RESOURCE_TYPE, decompress = false,
    decompressDir = ''): mttModels.TestResourceObj {
  return {
    name,
    url,
    cache_url: cacheUrl,
    test_resource_type: testResourceType,
    decompress,
    decompress_dir: decompressDir,
  };
}

/** Creates a list of new test resource objects */
export function newMockTestResourceObjs(): mttModels.TestResourceObj[] {
  return [
    newMockTestResourceObj(
        'name1', 'url1', 'cacheUrl1', mttModels.TestResourceType.DEVICE_IMAGE,
        false),
    newMockTestResourceObj(
        'name2', 'url2', 'cacheUrl2', mttModels.TestResourceType.UNKNOWN, true,
        'dir2'),
  ];
}

/** Creates a new Test Run given an id and test (state is optional) */
export function newMockTestRun(
    test: mttModels.Test, id = TEST_RUN_ID, state = TEST_RUN_STATE,
    testResources: mttModels.TestResourceObj[] = [],
    testPackageInfo?: mttModels.TestPackageInfo,
    testDevices?: tfcModels.DeviceInfo[], failedTestCount = FAILED_TEST_COUNT,
    totalTestCount = TOTAL_TEST_COUNT) {
  return {
    id,
    test,
    test_package_info: testPackageInfo,
    test_devices: testDevices,
    test_resources: testResources,
    test_run_config: newMockTestRunConfig(test.id!),
    state,
    failed_test_count: FAILED_TEST_COUNT,
    total_test_count: TOTAL_TEST_COUNT,
    create_time: DATE,
    update_time: DATE,
  };
}

/** Creates a new Test Run Config given a testid */
export function newMockTestRunConfig(
    testId: string, command = TEST_COMMAND, retryCommand = TEST_RETRY_COMMAND,
    runTarget = RUN_TARGET_STRING, shardCount = 1) {
  return {
    test_id: testId,
    cluster: CLUSTER,
    command,
    retry_command: retryCommand,
    device_specs: [],
    run_target: runTarget,
    run_count: 1,
    shard_count: shardCount,
    sharding_mode: mttModels.ShardingMode.RUNNER,
    max_retry_on_test_failures: 1,
    output_idle_timeout_seconds: 3600,
    queue_timeout_seconds: 100,
    before_device_action_ids: [],
    allow_partial_device_match: false,
  };
}

/** Creates a new Test Run Output object */
export function newMockTestRunOutput(
    lines = TEST_RUN_OUTPUT_LINES, offset = 0) {
  return {
    length: (lines.join('')).length,
    lines,
    offset,
  };
}

/** Creates a new TradefedConfigObject */
export function newMockTradefedConfigObject(
    className = TARGET_PREPARER_CLASS_NAME) {
  return {
    class_name: className,
    option_values: [],
  };
}

/** Creates a list of TradefedConfigObject */
export function newMockTradefedConfigObjectList() {
  return [
    newMockTradefedConfigObject('className1'),
    newMockTradefedConfigObject('className2'),
    newMockTradefedConfigObject('className3'),
  ];
}

/** Creates a new PrivateNodeConfig */
export function newMockPrivateNodeConfig(
    metricsEnabled = false, setupWizardCompleted = false, gmsClientId = '') {
  return {
    metrics_enabled: metricsEnabled,
    // Add field only if it's true
    ...gmsClientId && {gms_client_id: gmsClientId},
    ...setupWizardCompleted && {setup_wizard_completed: setupWizardCompleted},
  };
}

/** Creates a new mock TestModuleResult object */
export function newMockTestModuleResult(
    id = 'module_id',
    name = 'module.name',
    passedTests = 0,
    failedTests = 0,
    totalTests = 0,
    errorMessage?: string,
    ): mttModels.TestModuleResult {
  return {
    id,
    attempt_id: 'attempt_id',
    name,
    complete: !!errorMessage,
    passed_tests: passedTests,
    failed_tests: failedTests,
    total_tests: totalTests,
    error_message: errorMessage,
  } as mttModels.TestModuleResult;
}

/** Creates a new mock TestCaseResult object */
export function newMockTestCaseResult(
    moduleId = 'module_id', name = 'testName',
    status = mttModels.TestStatus.PASS, errorMessage = 'failure message',
    stackTrace = 'some stack trace'): mttModels.TestCaseResult {
  return {
    id: 'test_id',
    module_id: moduleId,
    name,
    status,
    error_message: errorMessage,
    stack_trace: stackTrace,
  } as mttModels.TestCaseResult;
}

/** Creates a new mock FileCleanerOperation object */
export function newMockFileCleanerOperation(
    type = mttModels.FileCleanerOperationType.ARCHIVE,
    params?: mttModels.NameValuePair[]) {
  return {
    type,
    params,
  } as mttModels.FileCleanerOperation;
}

/** Creates a new mock FileCleanerCriterion object */
export function newMockFileCleanerCriterion(
    type = mttModels.FileCleanerCriterionType.LAST_ACCESS_TIME,
    params?: mttModels.NameValuePair[]) {
  return {
    type,
    params,
  } as mttModels.FileCleanerCriterion;
}

/** Creates a new mock FileCleanerPolicy object */
export function newMockFileCleanerPolicy(
    name = 'policyName', target = mttModels.FileCleanerTargetType.FILE,
    operation?: mttModels.FileCleanerOperation,
    criteria?: mttModels.FileCleanerCriterion[]) {
  return {
    name,
    target,
    operation: operation || newMockFileCleanerOperation(),
    criteria,
  } as mttModels.FileCleanerPolicy;
}

/** Creates a new mock FileCleanerConfig object */
export function newMockFileCleanerConfig(
    name = 'configName', description?: string, directories: string[] = [],
    policyNames: string[] = []) {
  return {
    name,
    description,
    directories,
    policy_names: policyNames,
  } as mttModels.FileCleanerConfig;
}

/** Creates a new mock NetdataAlarmList object */
export function newMockNetdataAlarmList(
    hostname = 'hostname', id = 1, name = 'alarm', value = '',
    status = mttModels.NetdataAlarmStatus.WARNING) {
  return {
    alarms: [
      {
        hostname,
        id,
        name,
        value,
        status,
      } as mttModels.NetdataAlarm,
    ],
  } as mttModels.NetdataAlarmList;
}

/*******************************************
 * Functions to create mock TFC API objects
 *******************************************/

/** Creates a new Command */
export function newMockCommand(
    id = COMMAND_ID, requestId = REQUEST_ID,
    state = COMMAND_STATE): tfcModels.Command {
  return {
    id,
    request_id: requestId,
    state,
  };
}

/** Creates a new Command Attempt */
export function newMockCommandAttempt(
    failedTestCount?: number, passedTestCount?: number, requestId = REQUEST_ID,
    commandId = COMMAND_ID, attemptId = ATTEMPT_ID, state = COMMAND_STATE,
    startTime = DATE, endTime = DATE_FUTURE,
    hostname = HOSTNAME): tfcModels.CommandAttempt {
  return {
    request_id: requestId,
    command_id: commandId,
    attempt_id: attemptId,
    state,
    failed_test_count: failedTestCount,
    passed_test_count: passedTestCount,
    start_time: startTime,
    end_time: endTime,
    hostname,
  };
}

/** Creates a new Request */
export function newMockRequest(
    commands: tfcModels.Command[] = [],
    commandAttempts: tfcModels.CommandAttempt[] = [], id = REQUEST_ID,
    state = REQUEST_STATE): tfcModels.Request {
  return {id, state, commands, command_attempts: commandAttempts};
}

/*****************************************
 * Functions to create other mock objects
 *****************************************/

/**
 * Make a File object with custom text content
 * @param text Custom text content
 */
export function newMockFile(text: string, fileName: string) {
  return new File([new Blob([text], {type: 'text/plain'})], fileName);
}

/*******************
 * Helper functions
 *******************/

/**
 * Adds time to a Date
 *
 * @param date the starting date
 * @param hours number of hours to add
 * @param minutes number of minutes to add
 * @param seconds number of seconds to add
 * @return a new Date with the inputted amount of time added
 */
export function addTime(
    date: string, hours: number, minutes: number, seconds: number) {
  return moment(date)
      .add(hours, 'hours')
      .add(minutes, 'minutes')
      .add(seconds, 'seconds')
      .toISOString();
}

/**
 * Convert a string to title case (e.g. abc abc -> Abc Abc, ABC ABC -> Abc Abc)
 *
 * @param str a string that needs to be converted
 * @return a converted string
 */
export function toTitleCase(str: string) {
  return str.replace(
      /\w+/g,
      (word) =>
          `${word.charAt(0).toUpperCase()}${word.substr(1).toLowerCase()}`);
}

/** Creates a Build object. */
export function newMockBuild(
    id = BUILD_ID, name = BUILD_NAME, fileUrl = BUILD_URL,
    labels = [LABEL1, LABEL2],
    detectionStatus = mttModels.XtsRequirementsDetectionStatus.NOT_STARTED) {
  return {
    id,
    name,
    file_url: fileUrl,
    size: 123123123,
    labels,
    xts_requirements: {
      detection_status: detectionStatus,
      detection_test_run_id: TEST_RUN_ID,
      required_reports: [
        {
          'type': mttModels.ReportType.GTS,
          'test_plan': 'gts-interactive',
        },
        {'type': mttModels.ReportType.CTS}
      ],
    },
  };
}
