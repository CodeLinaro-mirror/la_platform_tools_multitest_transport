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
import {Inject, Injectable} from '@angular/core';
import {merge, Observable, of as observableOf} from 'rxjs';
import {map} from 'rxjs/operators';

import {AnalyticsContext} from './analytics_service';
import {APP_DATA, AppData} from './app_data';
import * as mttLabModels from './mtt_lab_models';
import * as tfcModels from './tfc_models';
import {DeviceInfosResponse, InvocationStatus, Request} from './tfc_models';

/** Device states to return when excluding offline devices. */
export const ONLINE_DEVICE_STATES = ['Allocated', 'Available', 'Fastboot'];

/** Client for TFC API access */
@Injectable({
  providedIn: 'root',
})
export class TfcClient {
  /** URL for TFC API methods */
  tfcApiUrl = '/_ah/api/tradefed_cluster/v1';
  /** URL for MTT API methods */
  mttApiUrl = '/_ah/api/mtt/v1';
  /** URL for API methods. It can be MTT or TFC api. */
  apiUrl = this.tfcApiUrl;
  /** URL for TFC API unassign hosts. */
  unAssignHostsUrl = `/hosts/unassign`;
  /** URL for the TFC API that sets hosts' recovery states in a batch. */
  batchSetHostsRecoveryStatesUrl = `/hosts/batchSetRecoveryState`;
  /** URL for the TFC API that sets devices' recovery states in a batch. */
  batchSetDevicesRecoveryStatesUrl = `/devices/batchSetRecoveryState`;
  readonly defaultCount = 10;

  constructor(
      @Inject(APP_DATA) private readonly appData: AppData,
      private readonly http: HttpClient) {
    if (appData.isAtsLabInstance) {
      this.tfcApiUrl = '/api-proxy';
    }
    this.apiUrl = appData.isOmniLabBased ? this.mttApiUrl : this.tfcApiUrl;
    this.unAssignHostsUrl = `${this.tfcApiUrl}${this.unAssignHostsUrl}`;
    this.batchSetHostsRecoveryStatesUrl =
        `${this.tfcApiUrl}${this.batchSetHostsRecoveryStatesUrl}`;
    this.batchSetDevicesRecoveryStatesUrl =
        `${this.tfcApiUrl}${this.batchSetDevicesRecoveryStatesUrl}`;
  }

  getDeviceInfos(): Observable<DeviceInfosResponse> {
    // TODO: Revert 'count' parameter after adding pagination.
    const params = new HttpParams()
                       .appendAll({'device_states': ONLINE_DEVICE_STATES})
                       .append('count', 1000);
    return this.http.get<DeviceInfosResponse>(
        `${this.apiUrl}/devices`, {params});
  }

  getRequest(requestId: string): Observable<Request> {
    return this.http.get<Request>(
        `${this.apiUrl}/requests/${encodeURIComponent(requestId)}`);
  }

  listCommands(
      requestId: string, state?: tfcModels.CommandState,
      pageToken?: string): Observable<tfcModels.CommandMessageCollection> {
    let params = new HttpParams();
    if (state) {
      params = params.append('state', state);
    }
    if (pageToken) {
      params = params.append('page_token', pageToken);
    }
    return this.http.get<tfcModels.CommandMessageCollection>(
        `${this.apiUrl}/requests/${encodeURIComponent(requestId)}/commands`,
        {params});
  }

  getCommandStateStats(requestId: string):
      Observable<tfcModels.CommandStateStats> {
    return this.http.get<tfcModels.CommandStateStats>(
        `${this.apiUrl}/requests/${
            encodeURIComponent(requestId)}/commands/state_counts`);
  }

  listCommandAttempts(requestId: string, commandId: string):
      Observable<tfcModels.CommandAttemptMessageCollection> {
    return this.http.get<tfcModels.CommandAttemptMessageCollection>(
        `${this.apiUrl}/requests/${encodeURIComponent(requestId)}/commands/${
            encodeURIComponent(commandId)}/command_attempts`);
  }

  getRequestInvocationStatus(requestId: string): Observable<InvocationStatus> {
    return this.http.get<InvocationStatus>(`${this.tfcApiUrl}/requests/${
        encodeURIComponent(requestId)}/invocation_status`);
  }

  getAssignedHostsInfos(
      lab: string, timestamp?: Date, timestampOperator?: string):
      Observable<mttLabModels.LabHostInfosResponse> {
    const searchCriteria: mttLabModels.HostSearchCriteria = {
      lab,
      recoveryStates:
          [tfcModels.RecoveryState.ASSIGNED, tfcModels.RecoveryState.FIXED],
      timestamp,
      timestampOperator,
    };
    return this.getHostInfos(searchCriteria, tfcModels.DEFAULT_ALL_COUNT);
  }

  getDeviceHistory(
      serial: string, count = this.defaultCount, cursor?: string,
      backwards = false): Observable<mttLabModels.LabDeviceInfoHistoryList> {
    const params = this.getHttpParams(count, cursor, backwards);
    return this.http
        .get<tfcModels.DeviceInfoHistoryList>(
            `${this.apiUrl}/devices/${serial}/histories`, {params})
        .pipe(map(
            result => mttLabModels.convertToLabDeviceInfoHistoryList(result)));
  }

  getDeviceInfo(serial: string): Observable<mttLabModels.LabDeviceInfo> {
    return this.http
        .get<tfcModels.DeviceInfo>(`${this.apiUrl}/devices/${serial}`)
        .pipe(map(result => mttLabModels.convertToLabDeviceInfo(result)));
  }

  queryDeviceInfos(
      searchCriteria?: mttLabModels.DeviceSearchCriteria,
      count = this.defaultCount,
      cursor?: string,
      backwards = false,
      ): Observable<mttLabModels.LabDeviceInfosResponse> {
    let params = this.getHttpParams(count, cursor, backwards);
    if (searchCriteria && searchCriteria.lab &&
        searchCriteria.lab !== mttLabModels.ALL_OPTIONS_VALUE) {
      params = params.append('lab_name', searchCriteria.lab);
    }
    if (searchCriteria && searchCriteria.hostnames) {
      params = params.appendAll({'hostnames': searchCriteria.hostnames});
    }
    if (searchCriteria && searchCriteria.hostGroups) {
      params = params.appendAll({'host_groups': searchCriteria.hostGroups});
    }
    if (searchCriteria && searchCriteria.testHarness) {
      params = params.appendAll({'test_harnesses': searchCriteria.testHarness});
    }
    if (searchCriteria && searchCriteria.pools) {
      params = params.appendAll({'pools': searchCriteria.pools});
    }
    if (searchCriteria && searchCriteria.deviceStates) {
      params = params.appendAll({'device_states': searchCriteria.deviceStates});
    }
    if (searchCriteria && searchCriteria.runTargets) {
      params = params.appendAll({'run_targets': searchCriteria.runTargets});
    }
    if (searchCriteria && searchCriteria.deviceSerial) {
      params = params.appendAll({'device_serial': searchCriteria.deviceSerial});
    }
    if (searchCriteria && searchCriteria.extraInfo &&
        searchCriteria.extraInfo.length === 1) {
      params = params.append('flated_extra_info', searchCriteria.extraInfo[0]);
    }
    if (searchCriteria && searchCriteria.includeOfflineDevices === false &&
        (!searchCriteria.deviceStates || !searchCriteria.deviceStates.length)) {
      params = params.appendAll({'device_states': ONLINE_DEVICE_STATES});
    }
    return this.http
        .get<mttLabModels.LabDeviceInfosResponse>(
            `${this.apiUrl}/devices`, {params})
        .pipe(map(
            result => mttLabModels.convertToLabDeviceInfosResponse(result)));
  }

  getDeviceInfosFromHost(hostName: string):
      Observable<mttLabModels.LabDeviceInfosResponse> {
    const params = new HttpParams().set('hostname', hostName);
    return this.http
        .get<tfcModels.DeviceInfosResponse>(`${this.apiUrl}/devices`, {params})
        .pipe(map(
            result => mttLabModels.convertToLabDeviceInfosResponse(result)));
  }

  getDeviceNotes(
      serial: string, deviceNoteIds: number[] = [], count = this.defaultCount,
      cursor?: string, backwards = false): Observable<tfcModels.NoteList> {
    let params = this.getHttpParams(count, cursor, backwards);
    if (deviceNoteIds.length) {
      params = params.append('ids', deviceNoteIds.join(', '));
    }
    return this.http.get<tfcModels.NoteList>(
        `${this.tfcApiUrl}/devices/${serial}/notes`, {params});
  }

  getHostInfo(id: string): Observable<mttLabModels.LabHostInfo> {
    return this.http.get<tfcModels.HostInfo>(`${this.tfcApiUrl}/hosts/${id}`)
        .pipe(map(result => mttLabModels.convertToLabHostInfo(result)));
  }

  getHostInfos(
      searchCriteria?: mttLabModels.HostSearchCriteria,
      count = this.defaultCount, cursor?: string,
      backwards = false): Observable<mttLabModels.LabHostInfosResponse> {
    let params = this.getHttpParams(count, cursor, backwards);
    if (searchCriteria && searchCriteria.lab &&
        searchCriteria.lab !== mttLabModels.ALL_OPTIONS_VALUE) {
      params = params.append('lab_name', searchCriteria.lab);
    }
    if (searchCriteria?.isBad) {
      params = params.append('is_bad', searchCriteria.isBad.toString());
    }
    if (searchCriteria && searchCriteria.hostnames) {
      params = params.appendAll({'hostnames': searchCriteria.hostnames});
    }
    if (searchCriteria && searchCriteria.hostGroups) {
      params = params.appendAll({'host_groups': searchCriteria.hostGroups});
    }
    if (searchCriteria && searchCriteria.testHarness) {
      params = params.appendAll({'test_harnesses': searchCriteria.testHarness});
    }
    if (searchCriteria && searchCriteria.testHarnessVersions) {
      params = params.appendAll(
          {'test_harness_versions': searchCriteria.testHarnessVersions});
    }
    if (searchCriteria && searchCriteria.pools) {
      params = params.appendAll({'pools': searchCriteria.pools});
    }
    if (searchCriteria && searchCriteria.hostStates) {
      params = params.appendAll({'host_states': searchCriteria.hostStates});
    }
    if (searchCriteria && searchCriteria.recoveryStates) {
      params =
          params.appendAll({'recovery_states': searchCriteria.recoveryStates});
    }
    if (searchCriteria && searchCriteria.hostUpdateStates) {
      params = params.appendAll(
          {'host_update_states': searchCriteria.hostUpdateStates});
    }
    if (searchCriteria?.extraInfo?.length === 1) {
      params = params.append('flated_extra_info', searchCriteria.extraInfo[0]);
    }
    if (searchCriteria?.timestamp && searchCriteria?.timestampOperator) {
      params =
          params
              .append(
                  'timestamp.milliseconds',
                  searchCriteria.timestamp.getTime().toString())
              .append('timestamp_operator', searchCriteria.timestampOperator);
    }
    return this.http
        .get<tfcModels.HostInfosResponse>(`${this.apiUrl}/hosts`, {params})
        .pipe(
            map(result => mttLabModels.convertToLabHostInfosResponse(result)));
  }

  getMyLabInfos(isAdmin = false): Observable<mttLabModels.LabInfosResponse> {
    if (this.appData.userNickname) {
      if (isAdmin) {
        return this.http
            .get<tfcModels.LabInfosResponse>(`${this.tfcApiUrl}/labs`)
            .pipe(
                map(result => mttLabModels.convertToLabInfosResponse(result)));
      } else {
        const params =
            new HttpParams().set('owner', this.appData.userNickname || '');
        return this.http
            .get<tfcModels.LabInfosResponse>(`${this.tfcApiUrl}/labs`, {params})
            .pipe(
                map(result => mttLabModels.convertToLabInfosResponse(result)));
      }
    } else {
      return observableOf({labInfos: []});
    }
  }

  getLabInfo(labName: string): Observable<mttLabModels.LabInfo> {
    return this.http.get<tfcModels.LabInfo>(`${this.tfcApiUrl}/labs/${labName}`)
        .pipe(map(result => mttLabModels.convertToLabInfo(result)));
  }

  getLabInfos(): Observable<mttLabModels.LabInfosResponse> {
    return this.http.get<tfcModels.LabInfosResponse>(`${this.tfcApiUrl}/labs`)
        .pipe(map(result => mttLabModels.convertToLabInfosResponse(result)));
  }

  getClusterInfo(clusterId: string): Observable<mttLabModels.ClusterInfo> {
    return this.http
        .get<tfcModels.ClusterInfo>(`${this.tfcApiUrl}/clusters/${clusterId}`)
        .pipe(map(result => mttLabModels.convertToClusterInfo(result)));
  }

  getOfflineHostInfos(
      lab: string, timestamp?: Date, timestampOperator?: string):
      Observable<mttLabModels.LabHostInfosResponse> {
    if (this.appData.userNickname) {
      const searchCriteria: mttLabModels.HostSearchCriteria = {
        lab,
        isBad: true,
        timestamp,
        timestampOperator,
      };

      // TODO:Remove the count param. In the first phase,we set a big number to
      // get all hosts at a time.
      return this.getHostInfos(searchCriteria, tfcModels.DEFAULT_ALL_COUNT);
    } else {
      return observableOf(
          {host_infos: [], more: false, prevCursor: '', nextCursor: ''});
    }
  }

  getHostHistory(
      id: string, count = this.defaultCount, cursor?: string,
      backwards = false): Observable<mttLabModels.LabHostInfoHistoryList> {
    const params = this.getHttpParams(count, cursor, backwards);
    return this.http
        .get<tfcModels.HostInfoHistoryList>(
            `${this.apiUrl}/hosts/${id}/histories`, {params})
        .pipe(map(
            result => mttLabModels.convertToLabHostInfoHistoryList(result)));
  }

  getHostNotes(
      id: string, hostNoteIds: number[] = [], count = this.defaultCount,
      cursor?: string, backwards = false,
      includeDeviceNotes = true): Observable<tfcModels.NoteList> {
    let params = this.getHttpParams(count, cursor, backwards);
    params = params.append('include_device_notes', String(includeDeviceNotes));
    if (hostNoteIds && hostNoteIds.length) {
      params = params.append('ids', hostNoteIds.join(', '));
    }
    return this.http.get<tfcModels.NoteList>(
        `${this.tfcApiUrl}/hosts/${id}/notes`, {params});
  }

  /**
   * Get HostConfigs from TFC service.
   * The request only executes when the Observable is subscribed.
   * @param labName specifies which lab the host configs come from.
   * @param count specifies max host configs in the response.
   * @param cursor is the cursor to host config results page.
   * @return Observable of tfcModels.HostConfigList.
   */
  getHostConfigs(
      labName: string = '',
      count = this.defaultCount,
      cursor?: string,
      ): Observable<tfcModels.HostConfigList> {
    let params = this.getHttpParams(count, cursor);
    if (labName) {
      params = params.append('lab_name', labName);
    }
    return this.http.get<tfcModels.HostConfigList>(
        `${this.tfcApiUrl}/hosts/configs`, {params});
  }


  /**
   * Get host resource for a host from TFC service.
   * @param id the hostname.
   * @return Observable of tfcModels.HostResource or null.
   */
  getHostResource(id: string): Observable<mttLabModels.LabHostResource|null> {
    return this.http
        .get<tfcModels.HostResource>(
            `${this.tfcApiUrl}/hosts/${id}/resource`)
        .pipe(map(
            result => mttLabModels.convertToLabHostResource(result)));
  }

  /**
   * Get TestHarnessImages from TFC service.
   * The request only executes when the Observable is subscribed.
   * @param tagPrefix specifies tag prefix of the images.
   * @param count specifies max TestHarnessImages in the response.
   * @param cursor is the cursor to TestHarnessImages results page.
   * @return Observable of tfcModels.TestHarnessImageList.
   */
  getTestHarnessImages(
      tagPrefix: string = '',
      count = this.defaultCount,
      cursor?: string,
      ): Observable<tfcModels.TestHarnessImageList> {
    let params = this.getHttpParams(count, cursor);
    if (tagPrefix) {
      params = params.append('tag_prefix', tagPrefix);
    }
    return this.http.get<tfcModels.TestHarnessImageList>(
        `${this.tfcApiUrl}/test_harness_images`, {params});
  }

  getMyRecoveryHostInfos(labName: string = '', hostGroups: string[] = []):
      Observable<mttLabModels.LabHostInfosResponse> {
    let params =
        new HttpParams().set('assignee', this.appData.userNickname || '');
    if (labName) {
      params = params.append('lab_name', labName);
    }
    if (hostGroups && hostGroups.length) {
      params = params.append('host_group', hostGroups.join(','));
    }
    return this.http
        .get<tfcModels.HostInfosResponse>(`${this.tfcApiUrl}/hosts`, {params})
        .pipe(
            map(result => mttLabModels.convertToLabHostInfosResponse(result)));
  }

  getPredefinedMessages(
      labName: string, messageType: tfcModels.PredefinedMessageType):
      Observable<tfcModels.PredefinedMessagesResponse> {
    const params = new HttpParams()
                       .set('lab_name', labName)
                       .set('type', messageType)
                       .set('count', '10000');
    return this.http.get<tfcModels.PredefinedMessagesResponse>(
        `${this.tfcApiUrl}/predefined_messages`, {params});
  }

  createPredefinedMessage(predefinedMessageInfo:
                              mttLabModels.CreatePredefinedMessageInfo):
      Observable<tfcModels.PredefinedMessage> {
    const context = AnalyticsContext.create('predefined_message', 'create');
    const body = {
      'lab_name': predefinedMessageInfo.labName,
      'type': predefinedMessageInfo.predefinedMessageType,
      'content': predefinedMessageInfo.content,
    };
    return this.http.post<tfcModels.PredefinedMessage>(
        `${this.tfcApiUrl}/predefined_messages`, body, {context});
  }

  updatePredefinedMessage(id: number, content: string):
      Observable<tfcModels.PredefinedMessage> {
    const context = AnalyticsContext.create('predefined_message', 'update');
    const body = {
      'content': content,
    };
    return this.http.patch<tfcModels.PredefinedMessage>(
        `${this.tfcApiUrl}/predefined_messages/${id}`, body, {context});
  }

  deletePredefinedMessage(id: number): Observable<tfcModels.PredefinedMessage> {
    const context = AnalyticsContext.create('predefined_message', 'delete');
    return this.http.delete<tfcModels.PredefinedMessage>(
        `${this.tfcApiUrl}/predefined_messages/${id}`, {context});
  }

  createOrUpdateNote(noteInfo: mttLabModels.CreateOrUpdateNoteInfo):
      Observable<string> {
    const action = noteInfo.id ? 'update' : 'create';
    const body: tfcModels.CreateOrUpdateNote = {
      user: this.appData.userNickname || '',
      lab_name: noteInfo.labName,
      id: noteInfo.id || undefined,
      message: noteInfo.message || '',
      offline_reason: noteInfo.offlineReason || '',
      offline_reason_id: noteInfo.offlineReasonId || undefined,
      recovery_action: noteInfo.recoveryAction || '',
      recovery_action_id: noteInfo.recoveryActionId || undefined,
      hostname: noteInfo.hostname || '',
    };

    if (noteInfo.noteType === mttLabModels.NoteType.HOST) {
      const context = AnalyticsContext.create('host_note', action);
      return this.http.post<string>(
          `${this.tfcApiUrl}/hosts/${noteInfo.hostname}/notes`, body, {context});
    } else {
      const context = AnalyticsContext.create('device_note', action);
      body.device_serial = noteInfo.deviceSerial || '';
      return this.http.post<string>(
          `${this.tfcApiUrl}/devices/${noteInfo.deviceSerial}/notes`, body,
          {context});
    }
  }

  batchCreateOrUpdateDevicesNotesWithPredefinedMessage(
      notesInfo: mttLabModels.BatchCreateOrUpdateNotesInfo):
      Observable<tfcModels.NoteList> {
    const context =
        AnalyticsContext.create('device_note', 'batchCreateOrUpdateNotes');
    notesInfo.user = this.appData.userNickname || '';
    return this.http.post<tfcModels.NoteList>(
        `${this.tfcApiUrl}/devices/notes:batchUpdateNotesWithPredefinedMessage`,
        notesInfo, {context});
  }

  batchCreateOrUpdateHostsNotesWithPredefinedMessage(
      notesInfo: mttLabModels.BatchCreateOrUpdateNotesInfo):
      Observable<tfcModels.NoteList> {
    const context =
        AnalyticsContext.create('host_note', 'batchCreateOrUpdateNotes');
    notesInfo.user = this.appData.userNickname || '';
    return this.http.post<tfcModels.NoteList>(
        `${this.tfcApiUrl}/hosts/notes:batchUpdateNotesWithPredefinedMessage`,
        notesInfo, {context});
  }

  batchGetDeviceNotes(deviceSerial: string, noteIds: number[]):
      Observable<tfcModels.NotesResponse> {
    let params = new HttpParams();
    for (const id of noteIds) {
      params = params.append('ids', id.toString());
    }
    return this.http.get<tfcModels.NotesResponse>(
        `${this.tfcApiUrl}/devices/${deviceSerial}/notes:batchGet`, {params});
  }

  batchGetHostNotes(hostname: string, noteIds: number[]):
      Observable<tfcModels.NotesResponse> {
    let params = new HttpParams();
    for (const id of noteIds) {
      params = params.append('ids', id.toString());
    }
    return this.http.get<tfcModels.NotesResponse>(
        `${this.tfcApiUrl}/hosts/${hostname}/notes:batchGet`, {params});
  }

  /** Gets the latest notes of each device in batch. */
  batchGetDevicesLatestNotes(deviceSerials: string[]):
      Observable<tfcModels.NoteList> {
    return this.batchGetMerge<tfcModels.NoteList>(
        `${this.tfcApiUrl}/devices/latest_notes:batchGet`, deviceSerials,
        'device_serials');
  }

  batchDeleteHostNotes(hostname: string, ids: number[]): Observable<void> {
    let params = new HttpParams();
    for (const id of ids) {
      params = params.append('ids', id.toString());
    }
    return this.http.delete<void>(
        `${this.tfcApiUrl}/hosts/${hostname}/notes`, {params});
  }

  batchDeleteDeviceNotes(deviceSerial: string, ids: number[]):
      Observable<void> {
    let params = new HttpParams();
    for (const id of ids) {
      params = params.append('ids', id.toString());
    }
    return this.http.delete<void>(
        `${this.tfcApiUrl}/devices/${deviceSerial}/notes`, {params});
  }

  batchSetDevicesRecoveryStates(deviceRecoveryStateRequests:
                                    tfcModels.DeviceRecoveryStateRequest[]):
      Observable<void> {
    const context = AnalyticsContext.create('devices', 'setRecoveryStates');
    const body = {
      device_recovery_state_requests: deviceRecoveryStateRequests,
    } as tfcModels.DeviceRecoveryStateRequests;
    return this.http.post<void>(
        this.batchSetDevicesRecoveryStatesUrl, body, {context});
  }

  batchSetHostsRecoveryStates(hostRecoveryStateRequests:
                                  tfcModels.HostRecoveryStateRequest[]):
      Observable<void> {
    const context = AnalyticsContext.create('hosts', 'setRecoveryStates');
    const body = {
      host_recovery_state_requests: hostRecoveryStateRequests,
    } as tfcModels.HostRecoveryStateRequests;
    return this.http.post<void>(
        this.batchSetHostsRecoveryStatesUrl, body, {context});
  }

  batchUpdateHostMetadata(
      requestBody: tfcModels.BatchUpdateHostMetadataRequest,
      spliceNumber = 50): Observable<void> {
    const context = AnalyticsContext.create('hosts', 'batchUpdateHostMetadata');
    if (requestBody.user === undefined) {
      requestBody.user = this.appData.userNickname;
    }
    const hostnames = [...requestBody.hostnames];
    const batchUpdates = [];
    while (hostnames.length) {
      const requestBodySliced = {...requestBody};
      requestBodySliced.hostnames = hostnames.splice(0, spliceNumber);
      batchUpdates.push(this.http.post<void>(
          `${this.tfcApiUrl}/hosts/hostMetadata:batchUpdate`, requestBodySliced,
          {context}));
    }
    return merge(...batchUpdates);
  }

  /** Removes a device from host. */
  removeDevice(deviceSerial: string, hostname: string): Observable<void> {
    const context = AnalyticsContext.create('device', 'remove');
    let params = new HttpParams();
    if (hostname) {
      params = params.append('hostname', hostname);
    }
    return this.http.post<void>(
        `${this.tfcApiUrl}/devices/${deviceSerial}/remove`, null,
        {context, params});
  }

  /** Removes the host. */
  removeHost(hostname: string): Observable<void> {
    const context = AnalyticsContext.create('host', 'remove');
    return this.http.post<void>(
        `${this.tfcApiUrl}/hosts/${hostname}/remove`, null, {context});
  }

  /** Gets a list of filter hint by FilterHintType. */
  getFilterHintList(type: tfcModels.FilterHintType):
      Observable<tfcModels.FilterHintList> {
    const params = new HttpParams().set('type', type);
    return this.http.get<tfcModels.FilterHintList>(
        `${this.tfcApiUrl}/filterHints`, {params});
  }

  checkUserPermission(): Observable<tfcModels.UserPermission> {
    if (this.appData?.email) {
      const params = new HttpParams().set('email', this.appData.email);
      return this.http.get<tfcModels.UserPermission>(
          `${this.tfcApiUrl}/admins/check`, {params});
    } else if (this.appData?.isAtsLabInstance === false) {
      return observableOf({isAdmin: true});
    } else {
      return observableOf({isAdmin: false});
    }
  }

  getHttpParams(count = this.defaultCount, cursor = '', backwards = false):
      HttpParams {
    return new HttpParams({
      fromObject: {
        'count': count ? String(count) : '',
        'cursor': cursor || '',
        'backwards': String(backwards),
      }
    });
  }

  /**
   * Breaks batch get into smaller http get and merges into a single observable
   * to prevent long url request.
   */
  batchGetMerge<T>(
      url: string, ids: string[], idParamKey: string,
      spliceNumber = 15): Observable<T> {
    const batchGets = [];
    while (ids.length) {
      const idSplice = ids.splice(0, spliceNumber);
      let params = new HttpParams();
      for (const id of idSplice) {
        params = params.append(idParamKey, id);
      }
      batchGets.push(this.http.get<T>(url, {params}));
    }
    return merge(...batchGets);
  }
}
