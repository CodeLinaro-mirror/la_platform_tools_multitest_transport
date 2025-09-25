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


import {AppData} from '../services/app_data';
import * as mttLabModels from '../services/mtt_lab_models';
import * as tfcModels from '../services/tfc_models';
import {deepCopy} from '../shared/util';

// CONSTANTS;
const ALLOCATED_DEVICES = ['2', '4', '8', '0', '4', '0', '0', '5', '10'];
const AVAILABLE_DEVICES = ['3', '2', '5', '2', '0', '0', '0', '2', '10'];
const BATTERY_LEVEL = 85;
const BUILD_ID = 'QT';
const CONTENT = 'context text';
const COUNT = 15;
const DATE = new Date().toISOString();
const DEFAULT_DEVICE_NUMBER = 12;
const DEVICE_AVAILABLE_STATE = tfcModels.DeviceState.AVAILABLE;
const DEVICE_COUNT_TIME_STAMP = [
  DATE,
  new Date(Date.UTC(2019, 10, 12, 3, 0, 0)).toISOString(),
  DATE,
  new Date(Date.UTC(2019, 12, 6, 17, 42, 0)).toISOString(),
  DATE,
  new Date(Date.UTC(2020, 1, 29, 23, 51, 50)).toISOString(),
  DATE,
  new Date(Date.UTC(2020, 3, 1, 12, 16, 0)).toISOString(),
  DATE,
];
const DEVICE_GONE_STATE = tfcModels.DeviceState.GONE;
const DEVICE_NOTE_ID = '0';
const DEVICE_SERIAL = 'D12345';
const EVENT_TIME = new Date().toISOString().slice(0, 19);
const HIDDEN = false;
const HOST_GROUP = 'AndroidEngProdApiClusterClientFuncTest';
const HOST_STATE = tfcModels.HostState.RUNNING;
const HOSTNAME = 'host01';
const IS_DEV_MODE = true;
const LAB_NAME = 'MTV lab';
const MAC_ADDRESS = 'e0:ee:1b:da:16:b4';
const MESSAGE = 'MESSAGE';
const OFFLINE_DEVICES = ['5', '6', '3', '8', '4', '1', '2', '0', '0', '0'];
const OFFLINE_REASON = 'OFFLINE_REASON';
const POOLS = ['pool1', 'pool2'];
const PREDEFINED_MESSAGE_TYPE =
    tfcModels.PredefinedMessageType.DEVICE_OFFLINE_REASON;
const PRODUCT = 'hawk';
const PRODUCT_VARIANT = 'hawk';
const PRODUCT_NAME = 'hawk';
const RECOVERY_ACTION = 'RECOVERY_ACTION';
const RECOVERY_UNKNOWN_STATE = tfcModels.RecoveryState.UNKNOWN;
const RUN_TARGET = 'hawk';
const SDK_VERSION = '29';
const SERIAL = 'device1';
const SIM_OPERATOR = 'unknown';
const SIM_STATE = 'unknown';
const TEST_HARNESS = 'unknown';
const TEST_HARNESS_VERSION = 'version1';
const TEST_HARNESS_LIST = [
  tfcModels.TestHarness.TF, tfcModels.TestHarness.MH,
  tfcModels.TestHarness.GOATS
];
const TEST_HARNESS_REPO_NAME = 'fake-gcr.io/fake-harness-repo';
const TEST_RUNNER_START_TIME = DATE;
const TODAY = new Date();
const TOTAL_DEVICES = ['10', '12', '16', '10', '8', '1', '1', '7', '20'];
const TIMESTAMP = new Date().toISOString();
const USER = 'user';
const UTILIZATION = 0.011693121693121693;
const EMAIL = USER + '@mock.com';

/** An array of new device count summaries. */
export const DEVICE_COUNT_SUMMARIES: tfcModels.DeviceCountSummary[][] = [
  [
    {
      run_target: 'target1',
      total: '5',
      offline: '3',
      available: '1',
      allocated: '1',
    },
    {
      run_target: 'target2',
      total: '2',
      offline: '1',
      available: '0',
      allocated: '1',
    },
    {
      run_target: 'target3',
      total: '3',
      offline: '1',
      available: '1',
      allocated: '1',
    }
  ],
  [
    {
      run_target: 'target1',
      total: '3',
      offline: '0',
      available: '3',
      allocated: '0',
    },
    {
      run_target: 'target4',
      total: '5',
      offline: '3',
      available: '1',
      allocated: '1',
    },
    {
      run_target: 'target5',
      total: '4',
      offline: '3',
      available: '1',
      allocated: '0',
    }
  ],
  [
    {
      run_target: 'target2',
      total: '7',
      offline: '2',
      available: '1',
      allocated: '4',
    },
    {
      run_target: 'target5',
      total: '9',
      offline: '1',
      available: '5',
      allocated: '3',
    }
  ],
  [
    {
      run_target: 'target2',
      total: '4',
      offline: '3',
      available: '1',
      allocated: '0',
    },
    {
      run_target: 'target3',
      total: '6',
      offline: '5',
      available: '0',
      allocated: '1',
    },
  ],
  [
    {
      run_target: 'target1',
      total: '8',
      offline: '4',
      available: '3',
      allocated: '1',
    },
  ],
  [
    {
      run_target: 'target1',
      total: '1',
      offline: '1',
      available: '0',
      allocated: '0',
    },
  ],
  [
    {
      run_target: 'target1',
      total: '2',
      offline: '2',
      available: '0',
      allocated: '0',
    },
  ],
  [
    {
      run_target: 'target1',
      total: '7',
      offline: '0',
      available: '3',
      allocated: '4',
    },
  ],
  [
    {
      run_target: 'target1',
      total: '20',
      offline: '0',
      available: '10',
      allocated: '10',
    },
  ],
];

/** An array of new HostInfo. */
export const HOST_INFOS: tfcModels.HostInfo[] = [
  newMockHostInfo(
      'host1', tfcModels.TestHarness.TF, tfcModels.HostState.RUNNING, false,
      'lab-1', 'host group-1'),
  newMockHostInfo(
      'host2', tfcModels.TestHarness.TF, tfcModels.HostState.KILLING, false,
      'lab-1', 'host group-1', newMockHostExtraInfo(2),
      tfcModels.RecoveryState.ASSIGNED, 'user1', DEVICE_COUNT_SUMMARIES[2],
      newDateTimeIsoString(0, 1, 0), undefined, undefined, undefined, undefined,
      tfcModels.HostUpdateState.SHUTTING_DOWN),
  newMockHostInfo(
      'host3', tfcModels.TestHarness.TF, tfcModels.HostState.GONE, false,
      'lab-1', 'host group-1', newMockHostExtraInfo(7), undefined, undefined,
      DEVICE_COUNT_SUMMARIES[7], newDateTimeIsoString(0, 2, 0), undefined,
      undefined, undefined, undefined, tfcModels.HostUpdateState.TIMED_OUT),
  newMockHostInfo(
      'host4', tfcModels.TestHarness.TF, tfcModels.HostState.QUITTING, false,
      'lab-1', 'host group-1', newMockHostExtraInfo(3),
      tfcModels.RecoveryState.FIXED, 'user1', DEVICE_COUNT_SUMMARIES[3],
      newDateTimeIsoString(0, 2, 0), undefined, undefined, undefined, undefined,
      tfcModels.HostUpdateState.SHUTTING_DOWN),
  newMockHostInfo(
      'host5', tfcModels.TestHarness.TF, tfcModels.HostState.UNKNOWN, false,
      'lab-1', 'host group-1', newMockHostExtraInfo(4),
      tfcModels.RecoveryState.ASSIGNED, 'user1', DEVICE_COUNT_SUMMARIES[4],
      newDateTimeIsoString(0, 3, 0)),
  newMockHostInfo(
      'host6', tfcModels.TestHarness.TF, tfcModels.HostState.RUNNING, false,
      'lab-1', 'host group-2', newMockHostExtraInfo(6),
      tfcModels.RecoveryState.FIXED, 'user1', DEVICE_COUNT_SUMMARIES[6],
      newDateTimeIsoString(1, 1, 0), undefined, undefined, undefined, undefined,
      tfcModels.HostUpdateState.SYNCING),
  newMockHostInfo(
      'host7', tfcModels.TestHarness.TF, tfcModels.HostState.KILLING, false,
      'lab-1', 'host group-2'),
  newMockHostInfo(
      'host8', tfcModels.TestHarness.TF, tfcModels.HostState.GONE, false,
      'lab-1', 'host group-2'),
  newMockHostInfo(
      'host9', tfcModels.TestHarness.TF, tfcModels.HostState.RUNNING, false,
      'lab-1', 'host group-2', newMockHostExtraInfo(8),
      tfcModels.RecoveryState.ASSIGNED, 'user1', DEVICE_COUNT_SUMMARIES[8],
      newDateTimeIsoString(1, 2, 0)),
  newMockHostInfo(
      'host10', tfcModels.TestHarness.TF, tfcModels.HostState.UNKNOWN, false,
      'lab-1', 'host group-2'),
  newMockHostInfo(
      'host11', tfcModels.TestHarness.GOATS, tfcModels.HostState.RUNNING, false,
      'lab-1', 'host group-3', undefined, tfcModels.RecoveryState.FIXED,
      'user2'),
  newMockHostInfo(
      'host12', tfcModels.TestHarness.GOATS, tfcModels.HostState.KILLING, false,
      'lab-1', 'host group-3', undefined, tfcModels.RecoveryState.FIXED,
      'user2'),
  newMockHostInfo(
      'host13', tfcModels.TestHarness.GOATS, tfcModels.HostState.GONE, false,
      'lab-1', 'host group-3', undefined, tfcModels.RecoveryState.ASSIGNED,
      'user2'),
  newMockHostInfo(
      'host14', tfcModels.TestHarness.TF, tfcModels.HostState.QUITTING, false,
      'lab-1', 'host group-3', undefined, tfcModels.RecoveryState.ASSIGNED,
      'user2'),
  newMockHostInfo(
      'host15', tfcModels.TestHarness.TF, tfcModels.HostState.UNKNOWN, false,
      'lab-1', 'host group-3', undefined, tfcModels.RecoveryState.ASSIGNED,
      'user2'),
  newMockHostInfo(
      'host16', tfcModels.TestHarness.GOATS, tfcModels.HostState.RUNNING, false,
      'lab-1', 'host group-4'),
  newMockHostInfo(
      'host17', tfcModels.TestHarness.GOATS, tfcModels.HostState.KILLING, false,
      'lab-1', 'host group-4'),
  newMockHostInfo(
      'host18', tfcModels.TestHarness.GOATS, tfcModels.HostState.GONE, false,
      'lab-1', 'host group-4'),
  newMockHostInfo(
      'host19', tfcModels.TestHarness.MH, tfcModels.HostState.QUITTING, false,
      'lab-1', 'host group-5'),
  newMockHostInfo(
      'host20', tfcModels.TestHarness.MH, tfcModels.HostState.UNKNOWN, false,
      'lab-1', 'host group-5'),
  newMockHostInfo(
      'host21', tfcModels.TestHarness.MH, tfcModels.HostState.RUNNING, false,
      'lab-1', 'host group-6'),
  newMockHostInfo(
      'host22', tfcModels.TestHarness.MH, tfcModels.HostState.KILLING, false,
      'lab-1', 'host group-6'),
  newMockHostInfo(
      'host23', tfcModels.TestHarness.MH, tfcModels.HostState.GONE, false,
      'lab-1', 'host group-6'),
  newMockHostInfo(
      'host24', tfcModels.TestHarness.MH, tfcModels.HostState.QUITTING, false,
      'lab-1', 'host group-7'),
  newMockHostInfo(
      'host25', tfcModels.TestHarness.MH, tfcModels.HostState.UNKNOWN, false,
      'lab-1', 'host group-7'),
  newMockHostInfo(
      'host26', tfcModels.TestHarness.MH, tfcModels.HostState.RUNNING, false,
      'lab-1', 'host group-8'),
  newMockHostInfo(
      'host27', tfcModels.TestHarness.TF, tfcModels.HostState.KILLING, false,
      'lab-2', 'host group-2', newMockHostExtraInfo(1),
      tfcModels.RecoveryState.ASSIGNED, 'user2', DEVICE_COUNT_SUMMARIES[1]),
  newMockHostInfo(
      'host28', tfcModels.TestHarness.TF, tfcModels.HostState.GONE, false,
      'lab-2', 'host group-2', newMockHostExtraInfo(5),
      tfcModels.RecoveryState.ASSIGNED, 'user2', DEVICE_COUNT_SUMMARIES[5]),
  newMockHostInfo(
      'host29', tfcModels.TestHarness.TF, tfcModels.HostState.QUITTING, false,
      'lab-2', 'host group-2'),
  newMockHostInfo(
      'host30', tfcModels.TestHarness.TF, tfcModels.HostState.UNKNOWN, false,
      'lab-2', 'host group-2', newMockHostExtraInfo(5),
      tfcModels.RecoveryState.ASSIGNED, 'user2', DEVICE_COUNT_SUMMARIES[5],
      newDateTimeIsoString(0, 30, 0)),
  newMockHostInfo(
      'host31', tfcModels.TestHarness.MH, tfcModels.HostState.RUNNING, false,
      'lab-2', 'host group-3', undefined, tfcModels.RecoveryState.ASSIGNED,
      'user3'),
  newMockHostInfo(
      'host32', tfcModels.TestHarness.MH, tfcModels.HostState.KILLING, false,
      'lab-3', 'host group-3', undefined, tfcModels.RecoveryState.ASSIGNED,
      'user3'),
  newMockHostInfo(
      'host33', tfcModels.TestHarness.MH, tfcModels.HostState.GONE, false,
      'lab-3', 'host group-3', undefined, tfcModels.RecoveryState.ASSIGNED,
      'user3'),
  newMockHostInfo(
      'host34', tfcModels.TestHarness.MH, tfcModels.HostState.QUITTING, false,
      'lab-3', 'host group-3', undefined, tfcModels.RecoveryState.ASSIGNED,
      'user3'),
  newMockHostInfo(
      'host35', tfcModels.TestHarness.MH, tfcModels.HostState.UNKNOWN, false,
      'lab-3', 'host group-3', undefined, tfcModels.RecoveryState.ASSIGNED,
      'user3'),
  newMockHostInfo(
      'host36', tfcModels.TestHarness.MH, tfcModels.HostState.RUNNING, false,
      'lab-3', 'host group-4', undefined, tfcModels.RecoveryState.ASSIGNED,
      'user3'),
  newMockHostInfo(
      'host37', tfcModels.TestHarness.MH, tfcModels.HostState.KILLING, false,
      'lab-3', 'host group-4', undefined, tfcModels.RecoveryState.ASSIGNED,
      'user3'),
  newMockHostInfo(
      'host38', tfcModels.TestHarness.MH, tfcModels.HostState.GONE, false,
      'lab-3', 'host group-4', undefined, tfcModels.RecoveryState.ASSIGNED,
      'user3'),
  newMockHostInfo(
      'host39', tfcModels.TestHarness.GOATS, tfcModels.HostState.QUITTING,
      false, 'lab-3', 'host group-5', undefined,
      tfcModels.RecoveryState.ASSIGNED, 'user3'),
  newMockHostInfo(
      'host40', tfcModels.TestHarness.GOATS, tfcModels.HostState.UNKNOWN, false,
      'lab-3', 'host group-5', undefined, tfcModels.RecoveryState.ASSIGNED,
      'user3'),
  newMockHostInfo(
      'host41testlonghosttestlonghosttestlonghosttestlonghosttestlong longhost',
      tfcModels.TestHarness.GOATS, tfcModels.HostState.GONE, false, 'lab-1',
      'hostgroup-1longhostgrouplonghostgrouplonghostgrouplonghostgroup longhostgroup'),
  newMockHostInfo(
      'host43', tfcModels.TestHarness.GOATS, tfcModels.HostState.RUNNING, false,
      'lab-1', 'host group-1', newMockHostExtraInfo(1),
      tfcModels.RecoveryState.ASSIGNED, 'user1', DEVICE_COUNT_SUMMARIES[1],
      newDateTimeIsoString(0, 10, 5)),
  newMockHostInfo(
      'host44', tfcModels.TestHarness.MH, tfcModels.HostState.RUNNING, false,
      'lab-2', 'host group-2', newMockHostExtraInfo(2), null, '',
      DEVICE_COUNT_SUMMARIES[2]),
  newMockHostInfo(
      'host45', tfcModels.TestHarness.TF, tfcModels.HostState.RUNNING, false,
      'lab-1', 'host group-1', newMockHostExtraInfo(7),
      tfcModels.RecoveryState.ASSIGNED, undefined, DEVICE_COUNT_SUMMARIES[7],
      newDateTimeIsoString(0, 3, 0)),
  newMockHostInfo(
      'host46', tfcModels.TestHarness.GOATS, tfcModels.HostState.GONE, false,
      'lab-1', 'host group-3', undefined, tfcModels.RecoveryState.ASSIGNED,
      'user2', []),
];


/***********************************************
 * Functions to create mock TFC Device objects
 ***********************************************/

/** Creates a new mock DeviceInfo. */
export function newMockDeviceInfo(
    deviceSerial: string = DEVICE_SERIAL, deviceNoteId: string = DEVICE_NOTE_ID,
    state: tfcModels.DeviceState = DEVICE_AVAILABLE_STATE,
    hidden: boolean = HIDDEN, hostname: string = HOSTNAME,
    runTarget = RUN_TARGET, deviceType = tfcModels.DeviceType.PHYSICAL,
    timestamp: string = TIMESTAMP,
    testHarness: string = TEST_HARNESS,
    extraInfo: mttLabModels.KeyValuePair[] | null = null)
    : tfcModels.DeviceInfo {
  return {
    battery_level: String(BATTERY_LEVEL),
    build_id: BUILD_ID,
    device_serial: deviceSerial,
    device_type: deviceType,
    extra_info: extraInfo ? extraInfo : newMockDeviceExtraInfo(deviceNoteId),
    flated_extra_info:
        ['battery_level:80', 'sdk_version:10', 'sim_state:ABSENT'],
    hidden,
    host_group: HOST_GROUP,
    hostname,
    lab_name: LAB_NAME,
    note: newMockDeviceNote(0, deviceSerial, '', '', '', '', ''),
    product: PRODUCT,
    product_variant: PRODUCT_VARIANT,
    pools: POOLS,
    recovering_by: USER,
    run_target: runTarget,
    recovery_state: RECOVERY_UNKNOWN_STATE,
    sim_state: SIM_STATE,
    sim_operator: SIM_OPERATOR,
    state,
    test_harness: testHarness,
    timestamp,
    is_stub_device: false,
  };
}

/** Creates a new mock newMockDeviceExtraInfo. */
export function newMockDeviceExtraInfo(deviceNoteId: string = DEVICE_NOTE_ID):
    mttLabModels.KeyValuePair[] {
  return [
    {key: 'battery_level', value: String(BATTERY_LEVEL)},
    {key: 'build_id', value: BUILD_ID},
    {key: 'device_note_id', value: String(deviceNoteId)},
    {key: 'mac_address', value: MAC_ADDRESS},
    {key: 'product_name', value: PRODUCT_NAME},
    {key: 'product_variant', value: PRODUCT_VARIANT},
    {key: 'product', value: PRODUCT},
    {key: 'sdk_version', value: SDK_VERSION},
    {key: 'sim_operator', value: SIM_OPERATOR},
    {key: 'sim_state', value: SIM_STATE},
    {key: 'utilization', value: String(UTILIZATION)},
  ];
}

/** Creates a new mock DeviceNote. */
export function newMockDeviceNote(
    deviceNoteId: number, serial: string = SERIAL, message = MESSAGE,
    offlineReason = OFFLINE_REASON, recoveryAction = RECOVERY_ACTION,
    timestamp = TIMESTAMP, user = USER,
    eventTime = EVENT_TIME): tfcModels.Note {
  return {
    id: deviceNoteId,
    message: deviceNoteId ? `${message}-${deviceNoteId}` : '',
    offline_reason: deviceNoteId ? `${offlineReason}-${deviceNoteId}` : '',
    recovery_action: deviceNoteId ? `${recoveryAction}-${deviceNoteId}` : '',
    timestamp,
    user,
    type: tfcModels.NoteType.DEVICE_NOTE,
    cluster_id: '',
    hostname: '',
    device_serial: serial,
    event_time: eventTime,
  };
}

/** Creates a new mock DeviceInfo. */
export function newMockLabDeviceInfo(
    deviceSerial: string, deviceNoteId: number = Number(DEVICE_NOTE_ID),
    state: tfcModels.DeviceState = DEVICE_AVAILABLE_STATE,
    hidden: boolean = HIDDEN, hostname: string = HOSTNAME,
    timestamp: string = TIMESTAMP,
    testHarness: string = TEST_HARNESS): mttLabModels.LabDeviceInfo {
  return mttLabModels.convertToLabDeviceInfo(newMockDeviceInfo(
      deviceSerial, String(deviceNoteId), state, hidden, hostname, RUN_TARGET,
      tfcModels.DeviceType.PHYSICAL, timestamp, testHarness));
}

/** Creates a new mock DeviceInfoHistoryList. */
export function newMockDeviceInfoHistoryList(serial: string = SERIAL):
    tfcModels.DeviceInfoHistoryList {
  const deviceInfos: tfcModels.DeviceInfo[] = [];
  const deviceNoteIds: number[] = [101, 0, 0, 0, 0, 0, 102, 0, 0, 0];
  const dt = TODAY;
  for (let i = 0; i < 10; i++) {
    dt.setHours(dt.getHours() - 9);
    const state = i % 2 === 0 ? tfcModels.DeviceState.AVAILABLE :
                                tfcModels.DeviceState.GONE;
    deviceInfos.push(newMockDeviceInfo(
        serial, String(deviceNoteIds[i]), state, HIDDEN, HOSTNAME, RUN_TARGET,
        tfcModels.DeviceType.PHYSICAL, dt.toISOString()));
  }
  return {
    histories: deviceInfos,
    next_cursor: '',
    prev_cursor: '',
  };
}

/** This method returns a new mock LabDeviceInfosResponse. */
export function newMockLabDeviceInfosResponse(
    hostName: string = HOSTNAME, deviceNumber: number = DEFAULT_DEVICE_NUMBER):
    mttLabModels.LabDeviceInfosResponse {
  return mttLabModels.convertToLabDeviceInfosResponse(
      newMockDeviceInfosResponse(hostName, deviceNumber));
}

/** This method creates a new mock DeviceInfosResponse. */
export function newMockDeviceInfosResponse(
    hostName: string = HOSTNAME, deviceNumber: number = DEFAULT_DEVICE_NUMBER):
    tfcModels.DeviceInfosResponse {
  const deviceInfos: tfcModels.DeviceInfo[] = [];

  for (let i = 0; i < deviceNumber; i++) {
    deviceInfos.push(newMockDeviceInfo(
        `device${i + 1}`, '0',
        i % 2 ? DEVICE_AVAILABLE_STATE : DEVICE_GONE_STATE, HIDDEN, hostName));
  }
  return {
    device_infos: deviceInfos,
    more: false,
    next_cursor: 'next',
    prev_cursor: 'prev',
  };
}

/** Creates a new mock DeviceNoteList. */
export function newMockDeviceNoteList(
    serial: string, deviceNoteIds: number[] = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]):
    tfcModels.NoteList {
  const deviceNoteList: tfcModels.Note[] = [];
  const dt = new Date();
  for (const deviceNoteId of deviceNoteIds) {
    dt.setHours(dt.getHours() - 9);
    deviceNoteList.push(newMockDeviceNote(
        deviceNoteId, serial, MESSAGE, OFFLINE_REASON, RECOVERY_ACTION,
        dt.toISOString()));
  }
  return {
    notes: deviceNoteList,
    next_cursor: '',
    prev_cursor: '',
  };
}

/** Create a new mock response for batch get device notes. */
export function newMockBatchGetDeviceNotes(
    serial: string = SERIAL,
    deviceNoteIds: number[] =
        [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]): tfcModels.NotesResponse {
  const deviceNotes: tfcModels.Note[] = [];
  for (const deviceNoteId of deviceNoteIds) {
    deviceNotes.push(newMockDeviceNote(deviceNoteId, serial));
  }

  return {
    notes: deviceNotes,
    more: false,
  };
}

/** Creates a new mock newMockLabDeviceExtraInfo. */
export function newMockLabDeviceExtraInfo(
    deviceNoteId: number =
        Number(DEVICE_NOTE_ID)): mttLabModels.LabDeviceExtraInfo {
  return {
    battery_level: BATTERY_LEVEL,
    build_id: BUILD_ID,
    device_note_id: deviceNoteId,
    mac_address: MAC_ADDRESS,
    product_name: PRODUCT_NAME,
    product_variant: PRODUCT_VARIANT,
    product: PRODUCT,
    sdk_version: SDK_VERSION,
    sim_operator: SIM_OPERATOR,
    sim_state: SIM_STATE,
    utilization: UTILIZATION,
  };
}

/** Creates a new mock DevicesLatestNoteList. */
export function newMockDevicesLatestNoteList(deviceSerials: string[]):
    tfcModels.NoteList {
  const deviceNoteList: tfcModels.Note[] = [];
  const dt = new Date();
  let deviceNoteId = 1;
  for (const deviceSerial of deviceSerials) {
    dt.setHours(dt.getHours() - 9);
    deviceNoteList.push(newMockDeviceNote(
        deviceNoteId, deviceSerial, MESSAGE, OFFLINE_REASON, RECOVERY_ACTION,
        dt.toISOString()));
    deviceNoteId++;
  }
  return {
    notes: deviceNoteList,
    next_cursor: '',
    prev_cursor: '',
  };
}

/********************************************
 * Functions to create mock TFC Host objects
 ********************************************/

/** This method creates a new mock HostInfo. */
export function newMockHostInfo(
    hostname: string,
    testHarness: tfcModels.TestHarness = tfcModels.TestHarness.TF,
    hostState: tfcModels.HostState = HOST_STATE,
    hidden: boolean = HIDDEN,
    labName: string = LAB_NAME,
    hostGroup: string = HOST_GROUP,
    extraInfo: mttLabModels.KeyValuePair[] = newMockHostExtraInfo(0),
    recoveryState: tfcModels.RecoveryState|null =
        tfcModels.RecoveryState.UNKNOWN,
    assignee: string = '',
    deviceCountSummaries: tfcModels.DeviceCountSummary[] =
        DEVICE_COUNT_SUMMARIES[0],
    timestamp: string = TIMESTAMP,
    offlineDevices: string = OFFLINE_DEVICES[0],
    totalDevices: string = TOTAL_DEVICES[0],
    lastRecoveryTime: string = TIMESTAMP,
    pools: string[] = POOLS,
    updateState: tfcModels.HostUpdateState|null = null,
    updateStateDisplayMessage: string|null = null,
    ): tfcModels.HostInfo {
  return {
    extra_info: extraInfo,
    hidden,
    hostname,
    host_group: hostGroup,
    host_state: hostState,
    recovery_state: recoveryState,
    update_state: updateState,
    update_state_display_message: updateStateDisplayMessage,
    lab_name: labName,
    last_recovery_time: lastRecoveryTime,
    note: newMockHostNote(0, '', '', '', ''),
    pools,
    assignee,
    test_harness: testHarness,
    test_harness_version: TEST_HARNESS_VERSION,
    test_runner_start_time: TEST_RUNNER_START_TIME,
    timestamp,
    device_count_summaries: deviceCountSummaries,
    allocated_devices: '',
    available_devices: '',
    bad_reason: '',
    offline_devices: offlineDevices,
    total_devices: totalDevices,
    flated_extra_info: ['host_ip: 127.0.0.1', 'wi-fi: abc'],
  };
}

/** Creates a new mock LabHostInfo. */
export function newMockLabHostInfo(
    hostname: string,
    testHarness: tfcModels.TestHarness = tfcModels.TestHarness.TF,
    hostState: tfcModels.HostState = HOST_STATE,
    recoveryState: tfcModels.RecoveryState = tfcModels.RecoveryState.UNKNOWN,
    hidden: boolean = HIDDEN,
    labName: string = LAB_NAME,
    hostGroup: string = HOST_GROUP,
    extraInfo: mttLabModels.KeyValuePair[] = newMockHostExtraInfo(0),
    assignee: string = '',
    deviceCountSummaries: tfcModels.DeviceCountSummary[] =
        DEVICE_COUNT_SUMMARIES[0],
    pools = POOLS,
    updateState: tfcModels.HostUpdateState|null = null,
    updateStateDisplayMessage: string|null = null,
    ): mttLabModels.LabHostInfo {
  return mttLabModels.convertToLabHostInfo(newMockHostInfo(
      hostname, testHarness, hostState, hidden, labName, hostGroup, extraInfo,
      recoveryState, assignee, deviceCountSummaries, TIMESTAMP,
      OFFLINE_DEVICES[0], TOTAL_DEVICES[0], TIMESTAMP, pools, updateState,
      updateStateDisplayMessage));
}

/** Creates a new mock unconverted HostInfo. */
export function newMockUnconvertedHostInfo(
    hostname: string,
    testHarness: tfcModels.TestHarness = tfcModels.TestHarness.TF,
    hostState: tfcModels.HostState = HOST_STATE,
    hidden: boolean = HIDDEN,
    labName: string = LAB_NAME,
    hostGroup: string = HOST_GROUP,
    extraInfo: mttLabModels.LabHostExtraInfo = newMockLabHostExtraInfo(0),
    recoveryState: tfcModels.RecoveryState = tfcModels.RecoveryState.UNKNOWN,
    assignee: string = '',
    deviceCountSummaries: tfcModels.DeviceCountSummary[] =
        DEVICE_COUNT_SUMMARIES[0],
    lastRecoveryTime: string = TIMESTAMP,
    updateState: tfcModels.HostUpdateState|null = null,
    updateStateDisplayMessage: string|null = null,
    badReason: string = '',
    ): mttLabModels.LabHostInfo {
  return {
    extraInfo,
    hidden,
    hostname,
    host_group: hostGroup,
    host_state: hostState,
    recoveryState,
    lab_name: labName,
    lastRecoveryTime,
    note: newMockHostNote(0, '', '', '', ''),
    pools: POOLS,
    assignee,
    testHarness,
    testHarnessVersion: TEST_HARNESS_VERSION,
    test_runner_start_time: TEST_RUNNER_START_TIME,
    timestamp: TIMESTAMP,
    device_count_summaries: deviceCountSummaries,
    flatedExtraInfo: ['host_ip: 127.0.0.1', 'wi-fi: abc'],
    updateState,
    updateStateDisplayMessage,
    bad_reason: badReason,
  };
}

/** Gets a mock HostInfo from HOST_INFOS array. */
export function getMockHostInfo(hostname: string): tfcModels.HostInfo|
    undefined {
  return HOST_INFOS.find(host => host.hostname === hostname);
}

/** Gets a mock HostInfo from HOST_INFOS array. */
export function getMockLabHostInfo(hostname: string): mttLabModels.LabHostInfo|
    undefined {
  const hostInfo = getMockHostInfo(hostname);
  if (!hostInfo) {
    return hostInfo;
  }
  return mttLabModels.convertToLabHostInfo(hostInfo);
}

/** This method returns a new mock LabHostInfosResponse. */
export function newMockLabHostInfosResponse():
    mttLabModels.LabHostInfosResponse {
  return mttLabModels.convertToLabHostInfosResponse(newMockHostInfosResponse());
}

/** This method creates a new mock HostInfosResponse. */
export function newMockHostInfosResponse(pageSize: number = 999):
    tfcModels.HostInfosResponse {
  const hosts = deepCopy(HOST_INFOS);
  return {
    host_infos: hosts.length > pageSize ? hosts.splice(0, pageSize) : hosts,
    more: false,
    prev_cursor: 'prev',
    next_cursor: 'next',
  };
}

/** Create a new mock HostInfoHistoryList. */
export function newMockHostInfoHistoryList(hostname: string = HOSTNAME):
    tfcModels.HostInfoHistoryList {
  const hostInfos: tfcModels.HostInfo[] = [];
  const hostNoteIds: number[] = [0, 201, 0, 202, 0, 0, 203, 0, 0, 0];
  const dt = new Date();

  for (let i = 0; i < 10; i++) {
    dt.setHours(dt.getHours() - 2);
    const state =
        i % 2 === 0 ? tfcModels.HostState.RUNNING : tfcModels.HostState.KILLING;
    const extraInfo = newMockHostExtraInfo(0, hostNoteIds[i]);
    hostInfos.push(newMockHostInfo(
        hostname, TEST_HARNESS_LIST[i % 3], state, HIDDEN, LAB_NAME, HOST_GROUP,
        extraInfo));
  }
  return {
    histories: hostInfos,
    next_cursor: '',
    prev_cursor: '',
  };
}

/** Create a new mock HostNote. */
export function newMockHostNote(
    hostNoteId: number, hostname: string = HOSTNAME, message = MESSAGE,
    offlineReason = OFFLINE_REASON, recoveryAction = RECOVERY_ACTION,
    timestamp = TIMESTAMP, user = USER): tfcModels.Note {
  return {
    id: hostNoteId,
    message,
    offline_reason: offlineReason,
    recovery_action: recoveryAction,
    timestamp,
    user,
    type: tfcModels.NoteType.HOST_NOTE,
    cluster_id: '',
    hostname,
    device_serial: '',
  };
}

/** Create a new mock HostResource. */
export function newMockHostResource(hostname: string = HOSTNAME):
    tfcModels.HostResource {
  return {
    hostname,
    resource: JSON.stringify({
      'identifier': {'hostname': hostname},
      'attribute': [{'name': 'harness_version', 'value': 'aversion'}],
      'resource': [
        {
          'resource_name': 'disk_util',
          'resource_instance': '/tmp',
          'metric': [
            {'tag': 'used', 'value': '10%'},
            {'tag': 'free', 'value': '20%'},
          ],
          'timestamp': TIMESTAMP,
        },
        {
          'resource_name': 'memory',
          'metric': [
            {'tag': 'used', 'value': '10%'},
            {'tag': 'free', 'value': '20%'},
          ],
          'timestamp': TIMESTAMP,
        }
      ]
    }),
    update_timestamp: TIMESTAMP,
    event_timestamp: TIMESTAMP,
  };
}

/** Create mock mttLabModesl.LabHostResource */
export function newMockLabHostResource(hostname: string = HOSTNAME):
    mttLabModels.LabHostResource|null {
  return mttLabModels.convertToLabHostResource(newMockHostResource(hostname));
}

/** Create a new mock HostNoteList. */
export function newMockHostNoteList(
    hostname: string, hostNoteIds: number[] = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
    includeDeviceNotes: boolean = true): tfcModels.NoteList {
  const hostNoteList: tfcModels.Note[] = [];
  let even = false;
  let deviceNoteId = 101;
  for (const hostNoteId of hostNoteIds) {
    if (includeDeviceNotes && even) {
      hostNoteList.push(newMockDeviceNote(deviceNoteId));
      deviceNoteId++;
    } else {
      hostNoteList.push(newMockHostNote(hostNoteId, hostname));
      even = !even;
    }
  }
  return {
    notes: hostNoteList,
    next_cursor: '',
    prev_cursor: '',
  };
}

/** Create a new mock response for batch get host notes. */
export function newMockBatchGetHostNotes(
    hostname: string = HOSTNAME,
    hostNoteIds: number[] =
        [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]): tfcModels.NotesResponse {
  const hostNotes: tfcModels.Note[] = [];
  for (const hostNoteId of hostNoteIds) {
    hostNotes.push(newMockHostNote(hostNoteId, hostname));
  }

  return {
    notes: hostNotes,
    more: false,
  };
}

/** This method creates a new host extra info. */
export function newMockHostExtraInfo(
    index: number, hostNoteId: number = 0): mttLabModels.KeyValuePair[] {
  const extraInfo: mttLabModels.KeyValuePair[][] = [];
  for (let i = 0; i < TOTAL_DEVICES.length; i++) {
    extraInfo[i] = [
      {key: 'allocated_devices', value: ALLOCATED_DEVICES[i]},
      {key: 'available_devices', value: AVAILABLE_DEVICES[i]},
      {key: 'offline_devices', value: OFFLINE_DEVICES[i]},
      {key: 'total_devices', value: TOTAL_DEVICES[i]},
      {key: 'device_count_time_stamp', value: DEVICE_COUNT_TIME_STAMP[i]},
      {key: 'host_note_id', value: hostNoteId.toString()}
    ];
  }

  return extraInfo[index];
}

/** This method creates a new host extra info. */
export function newMockLabHostExtraInfo(
    index: number, hostNoteId: number = 0): mttLabModels.LabHostExtraInfo {
  const extraInfo: mttLabModels.LabHostExtraInfo[] = [];
  for (let i = 0; i < TOTAL_DEVICES.length; i++) {
    extraInfo[i] = {
      allocated_devices: ALLOCATED_DEVICES[i],
      available_devices: AVAILABLE_DEVICES[i],
      offline_devices: OFFLINE_DEVICES[i],
      total_devices: TOTAL_DEVICES[i],
      device_count_time_stamp: DEVICE_COUNT_TIME_STAMP[i],
      host_note_id: hostNoteId,
    };
  }

  return extraInfo[index];
}

/**
 * This method returns part of newMockHostInfosResponse() data, it is
 * filtered by a lab.
 */
export function newMockOfflineHostInfosByLabResponse(lab: string):
    tfcModels.HostInfosResponse {
  const hosts = newMockHostInfosResponse().host_infos!.filter(
      host => host.lab_name === lab &&
          (Number(mttLabModels.getKeyValue(
               host.extra_info!, 'offline_devices')) > 0 ||
           host.host_state === tfcModels.HostState.GONE));
  return {host_infos: hosts, more: false, prev_cursor: '', next_cursor: ''};
}

/**
 * Returns offline part of newMockLabHostInfosResponse() data, it is filtered
 * by a lab.
 */
export function newMockLabOfflineHostInfosByLabResponse(lab: string):
    mttLabModels.LabHostInfosResponse {
  const hosts = newMockLabHostInfosResponse().host_infos!.filter(
      host => host.lab_name === lab &&
          (Number(host.extraInfo.offline_devices) > 0 ||
           host.host_state === tfcModels.HostState.GONE));
  return {host_infos: hosts, more: false, prevCursor: '', nextCursor: ''};
}

/**
 * Returns assigned part of newMockLabHostInfosResponse() data, it is filtered
 * by a lab.
 */
export function newMockLabAssignedHostInfosByLabResponse(lab: string):
    mttLabModels.LabHostInfosResponse {
  const hosts = newMockLabHostInfosResponse().host_infos!.filter(
      host => host.lab_name === lab && host.assignee);
  return {host_infos: hosts, more: false, prevCursor: '', nextCursor: ''};
}

/** This method returns a new mock HostInfoHistoryList. */
export function newMockLabHostInfoHistoryList(hostname: string = HOSTNAME):
    mttLabModels.LabHostInfoHistoryList {
  return mttLabModels.convertToLabHostInfoHistoryList(
      newMockHostInfoHistoryList(hostname));
}

/** Creates a new date time iso string based on current time. */
export function newDateTimeIsoString(
    hours: number, minutes: number, seconds: number): string {
  const dt = new Date();
  dt.setHours(dt.getHours() + hours);
  dt.setMinutes(dt.getMinutes() + minutes);
  dt.setSeconds(dt.getSeconds() + seconds);
  return dt.toISOString();
}


/** Create a new mock app data. */
export function newMockAppData(
    isDevMode = IS_DEV_MODE, userNickname = USER, email = EMAIL,
    isAtsLabInstance = true): AppData {
  return {isDevMode, userNickname, email, isAtsLabInstance};
}

/** Creates a new lab info. */
export function newMockFilterHint(value: string): tfcModels.FilterHint {
  return {value};
}

/** Creates a new mock FilterHintList which type is POOL. */
export function newMockFilterHintList(
    type: tfcModels.FilterHintType,
    count: number = 10): tfcModels.FilterHintList {
  const filterHints = [];
  for (let i = 0; i < count; i++) {
    filterHints.push(newMockFilterHint(`${type}-${i}`));
  }
  return {
    filter_hints: filterHints,
  };
}

/** Creates a new raw lab info. */
export function newMockRawLabInfo(
    labName: string,
    owners: string[],
    hostUpdateStateSummary?: tfcModels.HostUpdateStateSummary,
    hostCountByHarnessVersion?: mttLabModels.KeyValuePair[],
    hostUpdateStateSummariesByVersion?: tfcModels.HostUpdateStateSummary[],
    ): tfcModels.LabInfo {
  return {
    lab_name: labName,
    owners,
    host_update_state_summary: hostUpdateStateSummary,
    host_count_by_harness_version: hostCountByHarnessVersion,
    host_update_state_summaries_by_version: hostUpdateStateSummariesByVersion,
  };
}

/** Creates a new raw cluster info. */
export function newMockRawClusterInfo(
    clusterId: string,
    hostUpdateStateSummary?: tfcModels.HostUpdateStateSummary,
    hostCountByHarnessVersion?: mttLabModels.KeyValuePair[],
    hostUpdateStateSummariesByVersion?: tfcModels.HostUpdateStateSummary[],
    ): tfcModels.ClusterInfo {
  return {
    cluster_id: clusterId,
    host_update_state_summary: hostUpdateStateSummary,
    host_count_by_harness_version: hostCountByHarnessVersion,
    host_update_state_summaries_by_version: hostUpdateStateSummariesByVersion,
  };
}

/** Creates a new mock LabInfosResponse. */
export function newMockLabInfosResponse(): mttLabModels.LabInfosResponse {
  return {
    labInfos: [
      newMockLabInfo('lab-1', ['user1', 'user2', 'user3']),
      newMockLabInfo('lab-2', ['user2', 'user3']),
      newMockLabInfo('lab-3', ['user3']),
      newMockLabInfo('lab-4', ['user4']),
      newMockLabInfo('lab-5', ['user5']),
    ],
  };
}

/** Creates a new mock LabRawInfosResponse. */
export function newMockRawLabInfosResponse(): tfcModels.LabInfosResponse {
  return {
    lab_infos: [
      newMockRawLabInfo('lab-1', ['user1', 'user2', 'user3']),
      newMockRawLabInfo('lab-2', ['user2', 'user3']),
      newMockRawLabInfo('lab-3', ['user3']),
      newMockRawLabInfo('lab-4', ['user4']),
      newMockRawLabInfo('lab-5', ['user5']),
    ],
  };
}

/** Creates a new mock LabInfosResponse which lab is owned by user1. */
export function newMockMyLabInfosResponse(): mttLabModels.LabInfosResponse {
  return {
    labInfos: [
      newMockLabInfo('lab-1', ['user1', 'user2', 'user3']),
    ],
  };
}

/** Creates a new mock RawLabInfosResponse which lab is owned by user1. */
export function newMockMyRawLabInfosResponse(): tfcModels.LabInfosResponse {
  return {
    lab_infos: [
      newMockRawLabInfo('lab-1', ['user1', 'user2', 'user3']),
    ],
  };
}

/** Creates a new mock LabInfo. */
export function newMockLabInfo(
    labName: string,
    owners: string[] = [],
    hostUpdateStateSummary: mttLabModels.HostUpdateStateSummary|null = null,
    hostCountByHarnessVersion: mttLabModels.KeyValuePair[]|null = null,
    hostUpdateStateSummariesByVersion: mttLabModels.HostUpdateStateSummary[]|
    null = null,
    ): mttLabModels.LabInfo {
  return {
    labName,
    owners,
    hostUpdateStateSummary,
    hostCountByHarnessVersion: hostCountByHarnessVersion || [],
    hostUpdateStateSummariesByVersion: hostUpdateStateSummariesByVersion || [],
  };
}

/** Creates a new mock ClusterInfo. */
export function newMockClusterInfo(
    clusterId: string,
    hostUpdateStateSummary: mttLabModels.HostUpdateStateSummary|null = null,
    hostCountByHarnessVersion: mttLabModels.KeyValuePair[]|null = null,
    hostUpdateStateSummariesByVersion: mttLabModels.HostUpdateStateSummary[]|
    null = null,
    ): mttLabModels.ClusterInfo {
  return {
    clusterId,
    hostUpdateStateSummary,
    hostCountByHarnessVersion: hostCountByHarnessVersion || [],
    hostUpdateStateSummariesByVersion: hostUpdateStateSummariesByVersion || [],
  };
}

/** Creates a mock predefined message. */
export function newMockPredefinedMessage(
    id: number, labName: string = LAB_NAME,
    type: tfcModels.PredefinedMessageType = PREDEFINED_MESSAGE_TYPE,
    content: string = CONTENT, usedCount: number = COUNT,
    createTimestamp: string = DATE): tfcModels.PredefinedMessage {
  return {
    id,
    lab_name: labName,
    type,
    content,
    used_count: usedCount,
    create_timestamp: createTimestamp,
  };
}

/** Creates a list of mock predefined message. */
export function newMockPredefinedMessagesResponse(
    messageType: tfcModels.PredefinedMessageType):
    tfcModels.PredefinedMessagesResponse {
  const predefinedMessages: tfcModels.PredefinedMessage[] = [];

  for (let i = 0; i < 10; i++) {
    const id = i + 1;
    const content = `context text ${id}`;
    predefinedMessages.push(
        newMockPredefinedMessage(id, LAB_NAME, messageType, content, COUNT));
  }

  return {
    predefined_messages: predefinedMessages,
  };
}

/** Creates a mock raw HostUpdateStateSummary from TFC response. */
export function newMockHostUpdateStateSummary(
    total: string = '30', pending: string = '5', syncing: string = '2',
    shuttingDown: string = '10', restarting: string = '10',
    timedOut: string = '1', errored: string = '1', succeeded: string = '1',
    unknown: string = '0',
    updateTimestamp: string = '2021-01-01T07:02:02.356030',
    targetVersion: string = 'v-default'): tfcModels.HostUpdateStateSummary {
  return {
    total,
    pending,
    syncing,
    shutting_down: shuttingDown,
    restarting,
    timed_out: timedOut,
    errored,
    succeeded,
    unknown,
    update_timestamp: updateTimestamp,
    target_version: targetVersion,
  };
}

/** Creates a mock host config. */
export function newMockHostConfig(
    hostname: string,
    labName: string = LAB_NAME,
    clusterName: string = HOST_GROUP,
    enableUiUpdate: boolean = false,
    ): tfcModels.HostConfig {
  return {
    hostname,
    lab_name: labName,
    cluster_name: clusterName,
    enable_ui_update: enableUiUpdate,
  };
}

/** Creates a list of mock host configs for testing. */
export function newMockHostConfigList(
    hostConfigs?: tfcModels.HostConfig[],
    nextCursor?: string,
    ): tfcModels.HostConfigList {
  if (hostConfigs === undefined) {
    hostConfigs =
        Array.from({length: 10}, (v, i) => newMockHostConfig(`host-${i}.com`));
  }
  return {
    host_configs: hostConfigs,
    next_cursor: nextCursor,
  };
}

/** Creates a mock test harness image. */
export function newMockTestHarnessImage(
    createTime: string = TIMESTAMP,
    digest: string,
    repoName: string = TEST_HARNESS_REPO_NAME,
    tags: string[] = [],
    testHarness: string = TEST_HARNESS,
    testHarnessVersion: string = TEST_HARNESS_VERSION,
    ): tfcModels.TestHarnessImage {
  return {
    digest,
    create_time: createTime,
    repo_name: repoName,
    tags,
    test_harness: testHarness,
    test_harness_version: testHarnessVersion,
  };
}

/** Creates a list of mock test harness images for testing. */
export function newMockTestHarnessImageList(
    testHarnessImages?: tfcModels.TestHarnessImage[],
    nextCursor?: string,
    ): tfcModels.TestHarnessImageList {
  if (testHarnessImages === undefined) {
    testHarnessImages = Array.from({length: 10}, (v, i) => {
      const digest = `digest-${i}`;
      const testHarnessVersion = `version-${i}`;
      const tags = [digest, testHarnessVersion];
      return newMockTestHarnessImage(
          undefined, digest, undefined, tags, undefined, testHarnessVersion);
    });
  }
  return {
    images: testHarnessImages,
    next_cursor: nextCursor,
  };
}

/** Creates a mock batchUpdateHostMetadataRequest. */
export function newMockBatchUpdateHostMetadataRequest(
    hostnames: string[] = [HOSTNAME],
    testHarnessImage: string =
        `${TEST_HARNESS_REPO_NAME}:${TEST_HARNESS_VERSION}`,
    user: string = USER,
    ): tfcModels.BatchUpdateHostMetadataRequest {
  return {
    hostnames,
    test_harness_image: testHarnessImage,
    user,
  };
}
