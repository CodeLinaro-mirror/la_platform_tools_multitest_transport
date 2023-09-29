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

// Align backend interface naming
// tslint:disable:enforce-name-casing
import {KeyValuePair} from './mtt_lab_models';


/** A big number for retrieving all data without pagination. */
export const DEFAULT_ALL_COUNT = 9999999;

/**
 * Device Info
 */
export declare interface DeviceInfo {
  /** device battery_level */
  readonly battery_level: string;
  /** build_id:  Current build ID in the device */
  readonly build_id?: string;
  /** cluster: physical cluster */
  readonly cluster?: string;
  /** device_serial: Serial identifying the device. It should be unique. */
  readonly device_serial: string;
  /** device_type: device type (e.g. marlin) */
  readonly device_type?: DeviceType;
  /** Extra info for the device. */
  readonly extra_info: KeyValuePair[];
  /** Flated extra info for the device. */
  readonly flated_extra_info: string[];
  /** hidden: device is hidden or not */
  readonly hidden?: boolean;
  /** hostname: The name of the host this device is connected to. */
  readonly hostname?: string;
  /** This device belong to which host group. */
  readonly host_group?: string;
  /** The lab’s name the device belongs to. */
  readonly lab_name?: string;
  /** mac_address: device mac address */
  readonly mac_address?: string;
  /** The note for device history. */
  note?: Note;
  /** All clusters, both physical cluster and virtual cluster. */
  readonly pools: string[];
  /** product: Device product (e.g. flounder) */
  readonly product: string;
  /** product_variant: device product variant */
  readonly product_variant?: string;
  /** A user name who is recovering the device. */
  readonly recovering_by?: string;
  /** The recovery state of the device. */
  recovery_state?: RecoveryState;
  /** run_target: device run target */
  readonly run_target?: string;
  /** sdk_version: SDK version of the device's build */
  readonly sdk_version?: string;
  /** sim_operator: sim card operator */
  readonly sim_operator?: string;
  /** sim_state: sim card state */
  readonly sim_state?: string;
  /** The latest state of the device. */
  readonly state: DeviceState;
  /** Test harness the device is running under. */
  readonly test_harness: string;
  /** timestamp: update timestamp */
  readonly timestamp: string;
  /** is_stub_device: if the device is a stub device */
  readonly is_stub_device: boolean;
  /** preconfigured_ip: IP address of the device, if it is remote */
  readonly preconfigured_ip?: string;
  /** preconfigured_device_num_offset: device number offset */
  readonly preconfigured_device_num_offset?: number;
}


/**
 * The status of a test invocation
 */
export declare interface InvocationStatus {
  readonly test_group_statuses?: TestGroupStatus[];
}

/**
 *  A TFC request to run a test
 */
export declare interface Request {
  /** request id */
  readonly id: string;
  /** command to run the test */
  readonly command_line?: string;
  /** time (seconds) to wait in queue before automatically cancelling */
  readonly queue_timeout_seconds?: number;
  /** why the request was cancelled */
  readonly cancel_reason?: string;
  /** device selection rules */
  readonly run_target?: string;
  /** number of times to run the test */
  readonly run_count?: number;
  /** number of shards (devices) to use */
  readonly shard_count?: number;
  /** state of the request */
  readonly state: RequestState;
  /** maximum number of times to retry if at least one test fails */
  readonly max_retry_on_test_failures?: number;
  /** List of children command */
  commands?: Command[];
  /** List of children command attempts */
  command_attempts?: CommandAttempt[];
}

/**
 * Possibles states for a TFC request
 */
export enum RequestState {
  UNKNOWN,
  QUEUED,
  RUNNING,
  CANCELED,
  COMPLETED,
  ERROR,
}

/**
 * The progress of a test group.
 */
export declare interface TestGroupStatus {
  readonly name: string;
  readonly total_test_count?: number;
  readonly completed_test_count?: number;
  readonly failed_test_count?: number;
  readonly passed_test_count?: number;
  readonly is_complete?: boolean;
  readonly elapsed_time?: number;
  readonly failure_message?: string;
}

/** A TFC command */
export declare interface Command {
  /** command id */
  readonly id: string;
  /** id for the parent request */
  readonly request_id: string;
  /** name */
  readonly name?: string;
  /** command line */
  readonly command_line?: string;
  /** state of the command */
  readonly state: CommandState;
  /** timestamp when the command started executing */
  readonly start_time?: string;
  /** timestamp when the command finished executing */
  readonly end_time?: string;
  /** timestamp when the command was created */
  readonly create_time?: string;
  /** timestamp when the command was last updated */
  readonly update_time?: string;
  /** total test count for the latest command attempt */
  readonly total_test_count?: number;
  /** failed test count for the latest command attempt */
  readonly failed_test_count?: number;
  /** passed test count for the latest command attempt */
  readonly passed_test_count?: number;
  /** failed test run count for the latest command attempt */
  readonly failed_test_run_count?: number;
}

/** Possible states for a command */
export enum CommandState {
  UNKNOWN = 'UNKNOWN',
  QUEUED = 'QUEUED',
  RUNNING = 'RUNNING',
  CANCELED = 'CANCELED',
  COMPLETED = 'COMPLETED',
  ERROR = 'ERROR',
  FATAL = 'FATAL',
}

/** Final states for a command */
export const FINAL_COMMAND_STATES: CommandState[] = [
  CommandState.COMPLETED,
  CommandState.ERROR,
  CommandState.FATAL,
  CommandState.CANCELED,
];

/** Returns true if the status is considered final, false otherwise */
export function isFinalCommandState(state: CommandState) {
  return FINAL_COMMAND_STATES.includes(state);
}

/** A list of commands */
export declare interface CommandMessageCollection {
  readonly commands: Command[];
  readonly page_token: string;
}

/** The number of commands with a specific state */
export declare interface CommandStateStat {
  readonly state: CommandState;
  readonly count: number;
}

/** List the number of commands for each state */
export declare interface CommandStateStats {
  readonly state_stats: CommandStateStat[];
  readonly create_time?: string;
}

/** A TFC command attempt */
export declare interface CommandAttempt {
  /** id of the parent request */
  readonly request_id: string;
  /** id of the parent command */
  readonly command_id: string;
  /** id of this attempt */
  readonly attempt_id: string;
  /** state of the command attempt */
  readonly state: CommandState;
  /** timestamp when the attempt started executing */
  readonly start_time?: string;
  /** timestamp when the attempt finished executing */
  readonly end_time?: string;
  /** timestamp when the attempt was created */
  readonly create_time?: string;
  /** timestamp when the attempt was last updated */
  readonly update_time?: string;
  /** user friendly error message (infra error) */
  readonly error?: string;
  /** message from the generated error */
  readonly error_reason?: string;
  /** a subprocess error message (test error) */
  readonly subprocess_command_error?: string;
  /** summary of the event */
  readonly summary?: string;
  /** number of tests run */
  readonly total_test_count?: number;
  /** number of failed tests */
  readonly failed_test_count?: number;
  /** number of passed tests */
  readonly passed_test_count?: number;
  /** number of modules failed */
  readonly failed_test_run_count?: number;
  /** hostname */
  readonly hostname: string;
}

/** A list of command attempts */
export declare interface CommandAttemptMessageCollection {
  readonly command_attempts: CommandAttempt[];
}

/** Possible states for a device. */
export enum DeviceState {
  ALLOCATED = 'ALLOCATED',
  AVAILABLE = 'AVAILABLE',
  CHECKING_AVAILABILITY = 'CHECKING_AVAILABILITY',
  DIRTY = 'DIRTY',
  DYING = 'DYING',
  FASTBOOT = 'FASTBOOT',
  GONE = 'GONE',
  IGNORED = 'IGNORED',
  INIT = 'INIT',
  LAMEDUCK = 'LAMEDUCK',
  MISSING = 'MISSING',
  PREPPING = 'PREPPING',
  UNAVAILABLE = 'UNAVAILABLE',
  UNKNOWN = 'UNKNOWN',
}

/** Possible type for a device.  */
export enum DeviceType {
  EMULATOR = 'EMULATOR',
  GCE = 'GCE',
  NULL = 'NULL',
  PHYSICAL = 'PHYSICAL',
  REMOTE = 'REMOTE',
  TCP = 'TCP',
  LOCAL_VIRTUAL = 'LOCAL_VIRTUAL',
  REMOTE_VIRTUAL = 'REMOTE_VIRTUAL',
}

/** Possible recovery states for a device or host. */
export enum RecoveryState {
  ASSIGNED = 'ASSIGNED',
  FIXED = 'FIXED',
  UNKNOWN = 'UNKNOWN',
  VERIFIED = 'VERIFIED',
}

/** Possible update states for a host. */
export enum HostUpdateState {
  UNKNOWN = 'UNKNOWN',
  PENDING = 'PENDING',
  SYNCING = 'SYNCING',
  SHUTTING_DOWN = 'SHUTTING_DOWN',
  RESTARTING = 'RESTARTING',
  TIMED_OUT = 'TIMED_OUT',
  ERRORED = 'ERRORED',
  SUCCEEDED = 'SUCCEEDED',
}

/** Possible test harness for a device or a host.  */
export enum TestHarness {
  TF = 'TRADEFED',
  MH = 'MOBILEHARNESS',
  GOATS = 'GOATS',
}

/** Response for user's permission. */
export declare interface UserPermission {
  isAdmin: boolean;
}

/** Response for note api call. */
export declare interface NoteList {
  /** notes: a list of DeviceNote. */
  notes?: Note[];
  prev_cursor: string;
  next_cursor: string;
}

/** Response for device history api call. */
export declare interface DeviceInfoHistoryList {
  /** history: a list of DeviceInfo. */
  histories?: DeviceInfo[];
  prev_cursor: string;
  next_cursor: string;
}

/** Response for device list api call. */
export declare interface DeviceInfosResponse {
  /** A list of RawDeviceInfo. */
  device_infos?: DeviceInfo[];
  /** Indicate whether there are more results. */
  more?: boolean;
  /** The begin cursor of next batch. */
  next_cursor?: string;
  prev_cursor?: string;
}

/** Possible states for a host. */
export enum HostState {
  UNKNOWN = 'UNKNOWN',
  GONE = 'GONE',
  RUNNING = 'RUNNING',
  QUITTING = 'QUITTING',
  KILLING = 'KILLING',
}

/** Extra device count info by run target. */
export declare interface DeviceCountSummary {
  /** Device run target. */
  readonly run_target: string;
  /** Total device count of the run target. */
  readonly total: string;
  /** Offline device count of the run target. */
  readonly offline: string;
  /** Available device count of the run target. */
  readonly available: string;
  /** Allocated device count of the run target.. */
  readonly allocated: string;
}

/** Info of a single host. */
export declare interface HostInfo {
  /** Extra info for the host. */
  readonly extra_info?: KeyValuePair[];
  /** Is the host hidden or not, hidden is used for soft delete. */
  readonly hidden: boolean;
  /** Unique host name. */
  readonly hostname: string;
  /** It’s actually Tradefed’s state on the host. */
  readonly host_state: string;
  /** The recovery state of the host. */
  readonly recovery_state: RecoveryState|null;
  /** Ex physical cluster. */
  readonly host_group: string;
  /** The lab’s name the device belongs to. */
  readonly lab_name: string;
  /**
   * Last time the notes of the host or the devices under the host is added or
   * updated. Or last time the host is marked as recovered.
   */
  readonly last_recovery_time: string;
  /** The note for host history. */
  note: Note;
  /** All ex virtual clusters this host belongs to including the host group. */
  readonly pools: string[];
  /** A user name who is assigned to recover the host. */
  readonly assignee: string;
  /** Currently includes "tradefed","MH" and "GOATS". */
  readonly test_harness: TestHarness;
  readonly test_harness_version: string;
  /** The start time of the host, seconds from 1970/1/1. */
  readonly test_runner_start_time: string;
  /** Last info update time. */
  readonly timestamp: string;
  /** Extra device count info by run target. */
  device_count_summaries?: DeviceCountSummary[];
  // TODO:Remove the old schema for host
  /** Old schema for backward compatibility: Allocated device count. */
  readonly allocated_devices?: string;
  /** Old schema for backward compatibility: Available device count. */
  readonly available_devices?: string;
  /** Old schema for backward compatibility: Offline device count. */
  readonly offline_devices?: string;
  /** Old schema for backward compatibility: Total device count. */
  readonly total_devices?: string;
  /** The reason for host bad state */
  readonly bad_reason: string;
  /** Flated extra info for the host. */
  readonly flated_extra_info: string[];
  /** Host update state. */
  readonly update_state: HostUpdateState|null;
  /** Detailed description for host update state. */
  readonly update_state_display_message: string|null;
}

/** Response for host history api call. */
export declare interface HostInfoHistoryList {
  /** history: a list of HostInfo. */
  histories?: HostInfo[];
  prev_cursor: string;
  next_cursor: string;
}

/** Info for create or update a single note. */
export declare interface CreateOrUpdateNote {
  user: string;
  lab_name: string;
  id?: number;
  message: string;
  offline_reason: string;
  offline_reason_id?: number;
  recovery_action: string;
  recovery_action_id?: number;
  hostname: string;
  device_serial?: string;
}

/** Response for host list api call. */
export declare interface HostInfosResponse {
  /** A list of HostInfo. */
  host_infos?: HostInfo[];
  /** Indicate whether there are more results. */
  more: boolean;
  prev_cursor: string;
  next_cursor: string;
}

/** Host update state summary for a lab or host group. */
export declare interface HostUpdateStateSummary {
  /** Total number of hosts. */
  total: string;
  /** Number of host in UNKNOWN state. */
  unknown: string;
  /** Number of host in PENDING state. */
  pending: string;
  /** Number of host in SYNCING state. */
  syncing: string;
  /** Number of host in SHUTTING_DOWN state. */
  shutting_down: string;
  /** Number of host in RESTARTING state. */
  restarting: string;
  /** Number of host in TIMED_OUT state. */
  timed_out: string;
  /** Number of host in ERRORED state. */
  errored: string;
  /** Number of host in SUCCEEDED state. */
  succeeded: string;
  /** Timestamp when the summary is updated. */
  update_timestamp: string;
  /** The test harness version which the hosts update to. */
  target_version?: string|null;
}

/** Host resource. */
export declare interface HostResource {
  readonly hostname: string;
  readonly update_timestamp?: string;
  readonly event_timestamp?: string;
  readonly resource?: string;
}

/** Info of a single lab. */
export declare interface LabInfo {
  /** Unique lab name. */
  readonly lab_name: string;
  /** Owners defined in a lab config. */
  readonly owners: string[];
  /** Host update state summary for the lab. */
  readonly host_update_state_summary?: HostUpdateStateSummary|null;
  /** Host counts by test harness versions in the lab. */
  readonly host_count_by_harness_version?: KeyValuePair[];
  /** Host update state summaries for each version. */
  readonly host_update_state_summaries_by_version?: HostUpdateStateSummary[];
}

/** Response for lab list api call. */
export declare interface LabInfosResponse {
  /** A list of RawLabInfo. */
  lab_infos?: LabInfo[];
}

/** Info of a single physical cluster. */
export declare interface ClusterInfo {
  /** A Unique cluster ID */
  readonly cluster_id: string;
  /** Host update state summary in the lab. */
  readonly host_update_state_summary?: HostUpdateStateSummary|null;
  /** Host counts by test harness versions in the lab. */
  readonly host_count_by_harness_version?: KeyValuePair[];
  /** Host update state summaries for each version. */
  readonly host_update_state_summaries_by_version?: HostUpdateStateSummary[];
}

/** Info of a single note. */
export declare interface Note {
  /** Unique note id. */
  readonly id: number;
  /** The actually notes. */
  readonly message: string;
  /** The reason the device is offline. */
  readonly offline_reason: string;
  /** The action taken to recover the device. */
  readonly recovery_action: string;
  /** Create or update time. */
  readonly timestamp: string;
  /** The data modifier. */
  readonly user: string;
  /** UNKNOWN, CLUSTER_NOTE, HOST_NOTE or DEVICE_NOTE. */
  readonly type: string;
  /** Name of the cluster. */
  readonly cluster_id: string;
  /** Name of the host. */
  readonly hostname: string;
  /** Device serial of the device. */
  readonly device_serial: string;
  /** Addional field for user to record note event time. */
  readonly event_time?: string;
}

/** Response for batch get notes. */
export declare interface NotesResponse {
  notes?: Note[];
  more: boolean;
}

/** Details of a single predefined message */
export declare interface PredefinedMessage {
  readonly content: string;
  readonly create_timestamp: string;
  readonly id: number;
  readonly lab_name: string;
  readonly type: PredefinedMessageType;
  readonly used_count: number;
}

/** Response for predefined message list api call. */
export declare interface PredefinedMessagesResponse {
  predefined_messages?: PredefinedMessage[];
  prev_cursor?: string;
  next_cursor?: string;
}
// tslint::enable:enforce-name-casing

/** Possible types for a predefined message. */
export enum PredefinedMessageType {
  DEVICE_OFFLINE_REASON = 'DEVICE_OFFLINE_REASON',
  DEVICE_RECOVERY_ACTION = 'DEVICE_RECOVERY_ACTION',
  HOST_OFFLINE_REASON = 'HOST_OFFLINE_REASON',
  HOST_RECOVERY_ACTION = 'HOST_RECOVERY_ACTION',
}

/** Possible type for a note.  */
export enum NoteType {
  UNKNOWN = 'UNKNOWN',
  CLUSTER_NOTE = 'CLUSTER_NOTE',
  HOST_NOTE = 'HOST_NOTE',
  DEVICE_NOTE = 'DEVICE_NOTE',
}

/** Possible type for a Filter hint.  */
export enum FilterHintType {
  POOL = 'POOL',
  LAB = 'LAB',
  RUN_TARGET = 'RUN_TARGET',
  HOST = 'HOST',
  TEST_HARNESS = 'TEST_HARNESS',
  TEST_HARNESS_VERSION = 'TEST_HARNESS_VERSION',
  DEVICE_STATE = 'DEVICE_STATE',
  HOST_STATE = 'HOST_STATE',
  HOST_GROUP = 'HOST_GROUP',
  UPDATE_STATE = 'UPDATE_STATE',
  PRODUCT = 'PRODUCT',
  PRODUCT_VARIANT = 'PRODUCT_VARIANT',
}

/** Info for a single hint. */
export interface FilterHint {
  value: string;
}

/** Response for filter hint api call. */
export declare interface FilterHintList {
  filter_hints: FilterHint[];
}

/** Request for setting a host's recovery state. */
export declare interface HostRecoveryStateRequest {
  hostname: string;
  recovery_state: RecoveryState;
  assignee?: string;
}

/** Request for setting hosts' recovery states. */
export declare interface HostRecoveryStateRequests {
  host_recovery_state_requests: HostRecoveryStateRequest[];
}

/** Request for setting a device's recovery state. */
export declare interface DeviceRecoveryStateRequest {
  hostname: string;
  device_serial: string;
  recovery_state: RecoveryState;
}

/** Request for setting devices' recovery states. */
export declare interface DeviceRecoveryStateRequests {
  device_recovery_state_requests: DeviceRecoveryStateRequest[];
}

/** Message of a single host config. */
export declare interface HostConfig {
  hostname: string;
  lab_name: string;
  cluster_name: string;
  enable_ui_update: boolean;
}

/** Response for list host configs. */
export declare interface HostConfigList {
  host_configs?: HostConfig[];
  next_cursor?: string;
}

/** Message of a single test harness image. */
export declare interface TestHarnessImage {
  create_time: string;
  digest: string;
  repo_name: string;
  tags: string[];
  test_harness: string;
  test_harness_version: string;
}

/** Response for list test harness images. */
export declare interface TestHarnessImageList {
  images?: TestHarnessImage[];
  next_cursor?: string;
}

/** Request for updating host metadata in batches. */
export declare interface BatchUpdateHostMetadataRequest {
  hostnames: string[];
  test_harness_image: string;
  user?: string;
}
