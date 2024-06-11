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

// TODO: Copy mtt_lab_model_test.ts from ATS lab
import * as tfcModels from './tfc_models';

/** The product id for Feedback service. */
export const FEEDBACK_PRODUCT_ID = '5164855';
/** The bucket id for Feedback service. */
export const FEEDBACK_BUCKET = 'm2_fishfood';
/** Replaceable string of the hostname in the logUrl. */
export const HOSTNAME = '$host$';
/** Replaceable string of the device serial in the logUrl. */
export const DEVICE_SERIAL = '$deviceSerial$';
/** Default value for select all options. */
export const ALL_OPTIONS_VALUE = 'All';
/** The massage for click remove device. */
export const REMOVE_DEVICE_MESSAGE =
    'Do you want to stop monitoring this device (the device is no longer physically connected to the host)? The device will show up again if reconnected.';

/** Possible type for a predefined message. */
export enum MessageType {
  OFFLINE_REASON = 'OFFLINE REASON',
  RECOVERY_ACTION = 'RECOVERY ACTION',
}

/** Possiable hardware for a predefined message. */
export enum MessageCategory {
  DEVICE = 'DEVICE',
  HOST = 'HOST',
}

/** Possible type for a note.  */
export enum NoteType {
  DEVICE = 'DEVICE',
  HOST = 'HOST',
}

/** Info of a single device with converted extraInfo. */
export declare interface LabDeviceInfo extends tfcModels.DeviceInfo {
  /** Extra info for the device. */
  extraInfo: LabDeviceExtraInfo;
  /** Flated extra info for the device. */
  readonly flatedExtraInfo: string[];
  latestNote?: tfcModels.Note;
}

// TODO: Use lowerCamelCase instead
// tslint:disable:enforce-name-casing
/** Extra info from a device. */
export declare interface LabDeviceExtraInfo {
  device_note_id: number;
  build_id: string;
  sdk_version: string;
  battery_level: number;
  [key: string]: string | number;
}

/** Response for device history api call. */
export declare interface LabDeviceInfoHistoryList {
  /** history: a list of LabDeviceInfo. */
  histories?: LabDeviceInfo[];
  prev_cursor: string;
  next_cursor: string;
}

/** Response for device list api call. */
export declare interface LabDeviceInfosResponse {
  /** A list of DeviceInfo. */
  deviceInfos?: LabDeviceInfo[];
  /** Indicate whether there are more results. */
  more: boolean;
  /** The begin cursor of next batch. */
  nextCursor?: string;
  prevCursor?: string;
}

/**
 * Data format for storing the parameters associated with the offline host
 * filters.
 */
export declare interface OfflineHostFilterParams {
  lab: string;
  hostGroups: string[];
  runTargets: string[];
  testHarness: string;
  lastCheckInOperator?: string;
  lastCheckInHours?: number;
}

/** Response for host list api call. */
export declare interface LabHostInfosResponse {
  /** A list of HostInfo. */
  host_infos?: LabHostInfo[];
  /** Indicate whether there are more results. */
  more: boolean;
  prevCursor: string;
  nextCursor: string;
}

/** Info of a single host. */
export declare interface LabHostInfo {
  /** Extra info for the host. */
  extraInfo: LabHostExtraInfo;
  /** Is the host hidden or not, hidden is used for soft delete. */
  hidden: boolean;
  /** Unique host name. */
  readonly hostname: string;
  /** It’s actually Tradefed’s state on the host. */
  readonly host_state: string;
  /** The recovery state of the host. */
  recoveryState: tfcModels.RecoveryState;
  /** Ex physical cluster. */
  readonly host_group: string;
  /** The lab’s name the device belongs to. */
  readonly lab_name: string;
  /**
   * Last time the notes of the host or the devices under the host is added or
   * updated. Or last time the host is marked as recovered.
   */
  readonly lastRecoveryTime: string;
  /** The note for host history. */
  note: tfcModels.Note;
  /** All ex virtual clusters this host belongs to including the host group. */
  readonly pools: string[];
  /** A user name who is assigned to recover the host. */
  assignee: string;
  /** Currently includes "tradefed","MH" and "GOATS". */
  readonly testHarness: tfcModels.TestHarness;
  readonly testHarnessVersion: string;
  /** The start time of the host, seconds from 1970/1/1. */
  readonly test_runner_start_time: string;
  /** Last info update time. */
  readonly timestamp: string;
  /** Extra device count info by run target. */
  device_count_summaries: tfcModels.DeviceCountSummary[];
  /** Flated extra info for the host. */
  readonly flatedExtraInfo: string[];
  /** Host update state. */
  updateState: tfcModels.HostUpdateState|null;
  /** Detailed description for host update state */
  updateStateDisplayMessage: string|null;
  /** The reason for host bad state */
  bad_reason: string|null;
}

/** Extra info from a host. */
export declare interface LabHostExtraInfo {
  allocated_devices: string;
  available_devices: string;
  offline_devices: string;
  total_devices: string;
  device_count_time_stamp: string;
  host_note_id: number;
  [key: string]: string | number;
}

/** Response for host history api call. */
export declare interface LabHostInfoHistoryList {
  /** history: a list of HostInfo. */
  histories?: LabHostInfo[];
  prev_cursor: string;
  next_cursor: string;
}

/** Host update state summary for a lab or host group. */
export declare interface HostUpdateStateSummary {
  /** Total number of hosts. */
  readonly total: number;
  /** Number of host in UNKNOWN state. */
  readonly unknown: number;
  /** Number of host in PENDING state. */
  readonly pending: number;
  /** Number of host in SYNCING state. */
  readonly syncing: number;
  /** Number of host in SHUTTING_DOWN state. */
  readonly shuttingDown: number;
  /** Number of host in RESTARTING state. */
  readonly restarting: number;
  /** Number of host in TIMED_OUT state. */
  readonly timedOut: number;
  /** Number of host in ERRORED state. */
  readonly errored: number;
  /** Number of host in SUCCEEDED state. */
  readonly succeeded: number;
  /** Timestamp when the summary is updated. */
  readonly updateTimestamp: string;
  /** The test harness version which the hosts update to. */
  readonly targetVersion: string|null;
}

/** Lab resource identifier type. */
declare interface LabResourceIdentifier {
  [key: string]: string;
}

/** Lab resource attribute type. */
declare interface LabResourceAttribute {
  readonly name: string;
  readonly value: string;
}

/** Lab resource metric type. */
declare interface LabResourceMetric  {
  readonly tag: string;
  readonly value: string;
}

/** A single lab resource resource type. */
declare interface LabResource {
  readonly resource_name: string;
  readonly resource_instance?: string|null;
  readonly metric: LabResourceMetric[];
  readonly timestamp: string;
}

/** Lab resources for an entity resource type. */
declare interface LabResources {
  readonly identifier: LabResourceIdentifier;
  readonly attribute: LabResourceAttribute[];
  readonly resource: LabResource[];
}

/** Host resource. */
export declare interface LabHostResource {
  readonly hostname: string;
  readonly update_timestamp: string|null;
  readonly event_timestamp: string|null;
  readonly resource: LabResources;
}

/**
 * Converts the value of tfc_models.HostResource into LabHostResource object.
 */
export function convertToLabHostResource(source: tfcModels.HostResource):
    LabHostResource|null {

  if (! source.resource) {
    return null;
  }
  const target: LabHostResource = {
    hostname: source.hostname,
    update_timestamp: source.update_timestamp || null,
    event_timestamp: source.event_timestamp || null,
    resource: JSON.parse(source.resource) as LabResources,
  };

  return target;
}

/** Info of a single lab. */
export declare interface LabInfo {
  /** Unique lab name. */
  readonly labName: string;
  /** Owners defined in a lab config. */
  readonly owners: string[];
  /** Host update state summary in the lab. */
  readonly hostUpdateStateSummary: HostUpdateStateSummary|null;
  /** Host counts by test harness versions in the lab. */
  readonly hostCountByHarnessVersion: KeyValuePair[];
  /** Host update state summaries for each version. */
  readonly hostUpdateStateSummariesByVersion?: HostUpdateStateSummary[];
}

/** Response for lab list api call. */
export declare interface LabInfosResponse {
  /** A list of LabInfo. */
  labInfos: LabInfo[];
}

/** Info of a single physical cluster. */
export declare interface ClusterInfo {
  /** A Unique cluster ID */
  readonly clusterId: string;
  /** Host update state summary in the lab. */
  readonly hostUpdateStateSummary: HostUpdateStateSummary|null;
  /** Host counts by test harness versions in the lab. */
  readonly hostCountByHarnessVersion: KeyValuePair[];
  /** Host update state summaries for each version. */
  readonly hostUpdateStateSummariesByVersion?: HostUpdateStateSummary[];
}

/** Info for create or update a device note or a host note. */
export interface CreateOrUpdateNoteInfo {
  user?: string;
  labName: string;
  /** Unique note id. */
  id?: number;
  noteType: NoteType;
  /** Required if noteType is HOST. */
  hostname?: string;
  /** Required if noteType is DEVICE. */
  deviceSerial?: string;
  message: string;
  offlineReason: string;
  offlineReasonId?: number;
  /** The action taken to recover the device. */
  recoveryAction: string;
  recoveryActionId?: number;
}

/** Infos for create or update multiple notes. */
export interface BatchCreateOrUpdateNotesInfo {
  user?: string;
  lab_name: string;
  notes: Array<Partial<tfcModels.Note>>;
  message?: string;
  offline_reason?: string;
  offline_reason_id?: number;
  /** The action taken to recover the device. */
  recovery_action?: string;
  recovery_action_id?: number;
  event_time?: string;
}

/** Info for creating a predefined message. */
export interface CreatePredefinedMessageInfo {
  labName: string;
  predefinedMessageType: tfcModels.PredefinedMessageType;
  content: string;
}

/** Total device count summary info for hosts. */
export declare interface TotalDeviceCountSummary {
  offlineDevices: number;
  allDevices: number;
}

function deviceCountSum(prev: string, next: string) {
  const sum = Number(prev) + Number(next);
  return sum.toString();
}

/**
 * Filters HostInfo and returns a new HostInfo with new device count related
 * info of a specific run target.
 */
export function filterHostInfoCount(
    host: LabHostInfo,
    runTargetInfos: tfcModels.DeviceCountSummary[]): LabHostInfo {
  const newHost = Object.assign({}, host);
  newHost.device_count_summaries = [...runTargetInfos];

  if (host.extraInfo) {
    const newExtraInfo = Object.assign({}, host.extraInfo);
    newExtraInfo.total_devices =
        runTargetInfos.map(x => x.total).reduce(deviceCountSum);
    newExtraInfo.offline_devices =
        runTargetInfos.map(x => x.offline).reduce(deviceCountSum);
    newHost.extraInfo = newExtraInfo;
  } else {
    newHost.extraInfo = {
      allocated_devices:
          runTargetInfos.map(x => x.allocated).reduce(deviceCountSum),
      available_devices:
          runTargetInfos.map(x => x.available).reduce(deviceCountSum),
      offline_devices:
          runTargetInfos.map(x => x.offline).reduce(deviceCountSum),
      total_devices: runTargetInfos.map(x => x.total).reduce(deviceCountSum),
      device_count_time_stamp: '',
      host_note_id: 0,
    };
  }
  return newHost;
}

/**
 * Converts the value of HostInfo.extra_info into LabHostExtraInfo object.
 */
export function convertToHostExtraInfo(
    source: KeyValuePair[], extraInfo: LabHostExtraInfo):
    LabHostExtraInfo {
  for (const entity of source) {
    if (entity.key === 'host_note_id') {
      extraInfo.host_note_id = !Number.isNaN(Number(entity.value))?
          Number(entity.value): 0;
    } else {
      extraInfo[entity.key] = entity.value;
    }
  }
  return extraInfo;
}

/**
 * Converts the HostInfo object which returned from backend into LabHostInfo.
 */
export function convertToLabHostInfo(source: tfcModels.HostInfo): LabHostInfo {
  const extraInfo: LabHostExtraInfo = {
    allocated_devices: source.allocated_devices || '0',
    available_devices: source.available_devices || '0',
    offline_devices: source.offline_devices || '0',
    total_devices: source.total_devices || '0',
    device_count_time_stamp: '',
    host_note_id: 0,
  };
  if (source.extra_info) {
    convertToHostExtraInfo(source.extra_info, extraInfo);
  }
  return {
    extraInfo,
    hidden: source.hidden,
    hostname: source.hostname,
    host_state: source.host_state,
    recoveryState: source.recovery_state || tfcModels.RecoveryState.UNKNOWN,
    host_group: source.host_group,
    lab_name: source.lab_name,
    lastRecoveryTime: source.last_recovery_time,
    note: source.note,
    pools: source.pools,
    assignee: source.assignee,
    bad_reason: source.bad_reason,
    testHarness: source.test_harness,
    testHarnessVersion: source.test_harness_version,
    test_runner_start_time: source.test_runner_start_time,
    timestamp: source.timestamp,
    device_count_summaries: source.device_count_summaries || [],
    flatedExtraInfo: source.flated_extra_info,
    updateState: source.update_state,
    updateStateDisplayMessage: source.update_state_display_message,
  };
}

/**
 * Converts the HostInfosResponse object which returned from backend into
 * LabHostInfosResponse.
 */
export function convertToLabHostInfosResponse(
    source: tfcModels.HostInfosResponse): LabHostInfosResponse {
  const target: LabHostInfosResponse = {
    host_infos: [],
    more: source.more,
    prevCursor: source.prev_cursor,
    nextCursor: source.next_cursor,
  };

  if (!source.host_infos) {
    return target;
  }

  target.host_infos =
      source.host_infos.map(hostInfo => convertToLabHostInfo(hostInfo));

  return target;
}

/**
 * Converts the LabInfosResponse object which returned from backend into
 * LabInfosResponse.
 */
export function convertToLabInfosResponse(source: tfcModels.LabInfosResponse):
    LabInfosResponse {
  const target: LabInfosResponse = {
    labInfos: [],
  };

  if (!source.lab_infos) {
    return target;
  }

  target.labInfos =
      source.lab_infos.map(hostInfo => convertToLabInfo(hostInfo));

  return target;
}

/**
 * Converts TFC HostUpdateStateSummary object into MTT Lab
 * HostUpdateStateSummary.
 */
export function convertToHostUpdateStateSummary(
    source: tfcModels.HostUpdateStateSummary): HostUpdateStateSummary {
  return {
    total: isNaN(Number(source.total)) ? 0 : Number(source.total),
    unknown: isNaN(Number(source.unknown)) ? 0 : Number(source.unknown),
    pending: isNaN(Number(source.pending)) ? 0 : Number(source.pending),
    syncing: isNaN(Number(source.syncing)) ? 0 : Number(source.syncing),
    shuttingDown:
        isNaN(Number(source.shutting_down)) ? 0 : Number(source.shutting_down),
    restarting: isNaN(Number(source.restarting)) ? 0 :
                                                   Number(source.restarting),
    succeeded: isNaN(Number(source.succeeded)) ? 0 : Number(source.succeeded),
    timedOut: isNaN(Number(source.timed_out)) ? 0 : Number(source.timed_out),
    errored: isNaN(Number(source.errored)) ? 0 : Number(source.errored),
    updateTimestamp: source.update_timestamp,
    targetVersion: source.target_version || null,
  };
}

/**
 * Converts the HostInfoHistoryList object which returned from backend into
 * LabHostInfoHistoryList.
 */
export function convertToLabHostInfoHistoryList(
    source: tfcModels.HostInfoHistoryList): LabHostInfoHistoryList {
  const target: LabHostInfoHistoryList = {
    histories: [],
    prev_cursor: source.prev_cursor,
    next_cursor: source.next_cursor
  };

  if (!source.histories) {
    return target;
  }
  const hostInfos: LabHostInfo[] = [];

  for (const hostInfo of source.histories) {
    hostInfos.push(convertToLabHostInfo(hostInfo));
  }

  target.histories = hostInfos;

  return target;
}

/**
 * Converts the DeviceInfo object which returned from backend into
 * LabDeviceInfo.
 */
export function convertToLabDeviceInfo(source: tfcModels.DeviceInfo):
    LabDeviceInfo {
  return {
    battery_level: source.battery_level,
    build_id: source.build_id,
    cluster: source.cluster,
    device_serial: source.device_serial,
    device_type: source.device_type,
    extra_info: source.extra_info,
    extraInfo: convertToDeviceExtraInfo(source.extra_info || []),
    flated_extra_info: source.flated_extra_info,
    flatedExtraInfo: source.flated_extra_info,
    hidden: source.hidden,
    hostname: source.hostname,
    host_group: source.host_group,
    lab_name: source.lab_name,
    mac_address: source.mac_address,
    note: source.note,
    pools: source.pools,
    product: source.product,
    product_variant: source.product_variant,
    recovering_by: source.recovering_by,
    recovery_state: source.recovery_state || tfcModels.RecoveryState.UNKNOWN,
    run_target: source.run_target,
    sdk_version: source.sdk_version,
    sim_operator: source.sim_operator,
    sim_state: source.sim_state,
    state: source.state,
    test_harness: source.test_harness,
    timestamp: source.timestamp,
    is_stub_device: source.is_stub_device,
    preconfigured_ip: source.preconfigured_ip,
    preconfigured_device_num_offset: source.preconfigured_device_num_offset,
  };
}

/**
 * Converts the value of DeviceInfo.extra_info into DeviceExtraInfo object.
 */
export function convertToDeviceExtraInfo(source: KeyValuePair[]):
    LabDeviceExtraInfo {
  const extraInfo: LabDeviceExtraInfo = {
    device_note_id: -1,
    build_id: 'UNKNOWN',
    sdk_version: 'UNKNOWN',
    battery_level: 0,
  };

  for (const entity of source) {
    if (['device_note_id', 'utilization'].includes(entity.key)) {
      extraInfo[entity.key] =
          !Number.isNaN(Number(entity.value)) ? Number(entity.value) : -1;
    } else if (entity.key === 'battery_level') {
      extraInfo[entity.key] =
          !Number.isNaN(Number(entity.value)) ? Number(entity.value) / 100 : 0;
    } else {
      extraInfo[entity.key] = entity.value;
    }
  }
  return extraInfo;
}

/**
 * Converts the DeviceInfoHistoryList object which returned from backend into
 * LabDeviceInfoHistoryList.
 */
export function convertToLabDeviceInfoHistoryList(
    source: tfcModels.DeviceInfoHistoryList): LabDeviceInfoHistoryList {
  const deviceInfoHistoryList = source.histories || [];
  return {
    histories: deviceInfoHistoryList.map(x => convertToLabDeviceInfo(x)),
    prev_cursor: source.prev_cursor,
    next_cursor: source.next_cursor,
  };
}
// tslint::enable:enforce-name-casing

/**
 * Converts the DeviceInfosResponse object which returned from backend into
 * LabDeviceInfosResponse.
 */
export function convertToLabDeviceInfosResponse(
    source: tfcModels.DeviceInfosResponse): LabDeviceInfosResponse {
  const target: LabDeviceInfosResponse = {
    deviceInfos: [],
    more: source.more || false,
    nextCursor: source.next_cursor,
    prevCursor: source.prev_cursor,
  };
  if (!source.device_infos) {
    return target;
  }
  const deviceInfos = source.device_infos;
  target.deviceInfos = deviceInfos.map(x => convertToLabDeviceInfo(x));
  return target;
}

/**
 * Converts the LabInfo object which returned from backend into LabInfo.
 */
export function convertToLabInfo(source: tfcModels.LabInfo): LabInfo {
  return {
    labName: source.lab_name,
    owners: source.owners,
    hostUpdateStateSummary: source.host_update_state_summary ?
        convertToHostUpdateStateSummary(source.host_update_state_summary) :
        null,
    hostCountByHarnessVersion: source.host_count_by_harness_version ?
        source.host_count_by_harness_version :
        [],
    hostUpdateStateSummariesByVersion:
        source.host_update_state_summaries_by_version ?
        source.host_update_state_summaries_by_version.map(
            summary => convertToHostUpdateStateSummary(summary)) :
        [],
  };
}

/**
 * Converts the LabInfo object which returned from backend into LabInfo.
 */
export function convertToClusterInfo(source: tfcModels.ClusterInfo):
    ClusterInfo {
  return {
    clusterId: source.cluster_id,
    hostUpdateStateSummary: source.host_update_state_summary ?
        convertToHostUpdateStateSummary(source.host_update_state_summary) :
        null,
    hostCountByHarnessVersion: source.host_count_by_harness_version ?
        source.host_count_by_harness_version :
        [],
    hostUpdateStateSummariesByVersion:
        source.host_update_state_summaries_by_version ?
        source.host_update_state_summaries_by_version.map(
            summary => convertToHostUpdateStateSummary(summary)) :
        [],
  };
}

/**
 * Converts category and message type into predefined message type.
 */
export function covertToPredefinedMessageType(
    category: string, type: string): tfcModels.PredefinedMessageType|undefined {
  let predefinedMessageType;

  if (!category || !type) {
    predefinedMessageType = undefined;
  } else {
    switch (true) {
      case category === MessageCategory.DEVICE &&
          type === MessageType.OFFLINE_REASON:
        predefinedMessageType =
            tfcModels.PredefinedMessageType.DEVICE_OFFLINE_REASON;
        break;
      case category === MessageCategory.DEVICE &&
          type === MessageType.RECOVERY_ACTION:
        predefinedMessageType =
            tfcModels.PredefinedMessageType.DEVICE_RECOVERY_ACTION;
        break;
      case category === MessageCategory.HOST &&
          type === MessageType.OFFLINE_REASON:
        predefinedMessageType =
            tfcModels.PredefinedMessageType.HOST_OFFLINE_REASON;
        break;
      case category === MessageCategory.HOST &&
          type === MessageType.RECOVERY_ACTION:
        predefinedMessageType =
            tfcModels.PredefinedMessageType.HOST_RECOVERY_ACTION;
        break;
      default:
        predefinedMessageType = undefined;
        break;
    }
  }
  return predefinedMessageType;
}

/** Calculates the total device count summary from hosts. */
export function calculateTotalDeviceCountSummary(hosts: LabHostInfo[]):
    TotalDeviceCountSummary {
  const totalDeviceCountSummary: TotalDeviceCountSummary = {
    offlineDevices: 0,
    allDevices: 0,
  };
  for (const host of hosts) {
    if (!host.extraInfo) {
      continue;
    }
    const Devices = !Number.isNaN(Number(host.extraInfo.total_devices)) ?
        Number(host.extraInfo.total_devices) :
        0;
    const offlineDevices =
        !Number.isNaN(Number(host.extraInfo.offline_devices)) ?
        Number(host.extraInfo.offline_devices) :
        0;
    totalDeviceCountSummary.allDevices += Devices;
    totalDeviceCountSummary.offlineDevices += offlineDevices;
  }

  return totalDeviceCountSummary;
}

/** Info for assigning hosts. */
export declare interface HostAssignInfo {
  hostnames: string[];
  assignee: string;
}

/** Info for searching hosts. */
export declare interface HostSearchCriteria {
  extraInfo?: string[];
  lab?: string;
  hostGroups?: string[];
  hostnames?: string[];
  hostStates?: string[];
  isBad?: boolean;
  pools?: string[];
  recoveryStates?: string[];
  testHarness?: string[];
  testHarnessVersions?: string[];
  timestamp?: Date;
  timestampOperator?: string;
  hostUpdateStates?: string[];
}

/** Info for host list query params. */
export declare interface HostQueryParams extends HostSearchCriteria {
  hostListPageToken?: string;
  hostListPageSize?: number;
}

/** Info for search devices. */
export declare interface DeviceSearchCriteria {
  lab?: string;
  hostnames?: string[];
  hostGroups?: string[];
  testHarness?: string[];
  pools?: string[];
  deviceStates?: string[];
  runTargets?: string[];
  deviceSerial?: string[];
  extraInfo?: string[];
  includeOfflineDevices?: boolean;
}

/** Info for device list query params. */
export declare interface DeviceQueryParams extends DeviceSearchCriteria {
  deviceListPageToken?: string;
  deviceListPageSize?: number;
}

/** Options for the filterbar. */
export interface FilterOption {
  value: string;
  selected: boolean;
  type: string;
  hidden: boolean;
  showCheckbox: boolean;
}

/** The param name for selected lab on the localStorage. */
export const LAB_STORAGE_KEY = 'Selected_Lab';

/** Modes for navigating to a page. */
export enum NavigatePageMode {
  DIALOG = 'DIALOG',
  PAGE = 'PAGE'
}

/**
 * Gets the value by key in a key value object({key:key,value:value}) array.
 */
export function getKeyValue(source: KeyValuePair[], key: string): string {
  const keyValue = source.find((x: KeyValuePair) => x.key === key);
  return keyValue ? keyValue.value : '';
}

/**
 * An interface that includes key and value properties.
 */
export declare interface KeyValuePair {
  readonly key: string;
  readonly value: string;
}

/** Possible type for a survey trigger. */
export enum SurveyTrigger {
  BATCH_ADD_DEVICES_NOTES = 'j16y8uk4g0nnvAQfLMD0UDJ3CopK',
  BATCH_ADD_HOSTS_NOTES = 'fHaBQs3fz0nnvAQfLMD0XwZjPxtc',
  DEVICE_FILTER_BAR = '9sLq3ZJWC0nnvAQfLMD0YeSABAhq',
  DEVICE_HISTORY = 'RkHvTe5wC0nnvAQfLMD0WkGyB83Z',
  DEVICE_NAVIGATION = 'fPkaarNKy0nnvAQfLMD0WesFhidw',
  ENTER_THE_SITE = 'RcEwf7CrV0nnvAQfLMD0RHV3tiMu',
  HOST_FILTER_BAR = 'nMod5VCMv0nnvAQfLMD0NSmC76F6',
  HOST_NAVIGATION = 'npoANuGPX0nnvAQfLMD0SfeA1iNn',
  HOST_NOTES = '1oFN4UQy90nnvAQfLMD0QFeaytzS',
  NOTES_EDITOR = 'esgEdv8r10nnvAQfLMD0U9h44xBR',
  OFFLINE_HOST_ASSIGNMENT = 'vhoV1QXd50nnvAQfLMD0RNa1SCXn',
  SORT_DEVICE_DATA = 'FVdKWz8Rh0nnvAQfLMD0XMNRsAwP',
  SORT_HOST_DATA = 'Mhw1SdE2c0nnvAQfLMD0Nm3fM3px',
  SEARCH_BOX = '7Wf2qJC9o0nnvAQfLMD0QW8NmeWz',
  SEARCHABLE_FILTER = 'pKJaTdaQK0nnvAQfLMD0VfULJyWr',
  VIEW_DEVICES_COLUMNS = 'S8E34xYdV0nnvAQfLMD0T3XM42Dw',
}

/** Gets the device serial for display. */
export function getDeviceSerialForDisplay(device: LabDeviceInfo) {
  if (device.device_type === tfcModels.DeviceType.REMOTE_VIRTUAL) {
    return `remote-virtual-${device.preconfigured_ip || 'unknown'}-${
        device.preconfigured_device_num_offset || 'unknown'}`;
  }
  return device.device_serial;
}
