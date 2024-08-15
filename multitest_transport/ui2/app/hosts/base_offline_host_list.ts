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

import {LiveAnnouncer} from '@angular/cdk/a11y';
import {Location} from '@angular/common';
import {ActivatedRoute, ParamMap, Router, UrlSerializer} from '@angular/router';
import {Observable, of as observableOf, OperatorFunction, pipe, ReplaySubject} from 'rxjs';
import {finalize, map, switchMap, take, takeUntil} from 'rxjs/operators';

import {ALL_OPTIONS_VALUE, HostAssignInfo, LabHostInfo, LabInfo, OfflineHostFilterParams, TotalDeviceCountSummary} from '../services/mtt_lab_models';
import {Notifier} from '../services/notifier';
import {TfcClient} from '../services/tfc_client';
import {DeviceCountSummary, HostRecoveryStateRequest, RecoveryState} from '../services/tfc_models';
import {UserService} from '../services/user_service';
import {TimeFilterEvent, TimeFilterOperator} from '../shared/time_input_filter';
import {distinctArray} from '../shared/util';

type SingleValueField = 'lab'|'testHarness';
type MultipleValuesField = 'hostGroups'|'runTargets';

/**
 * A base class of OfflineHostList and OfflineHostAssignmentsPage. It provides
 * the shared fields and functions for filters.
 */
export class BaseOfflineHostList {
  protected readonly destroy = new ReplaySubject<void>();

  currentLabOwners: string[] = [];

  /** The labs that is selected for filtering the host list by user. */
  selectedLab = '';

  /** Host groups that are selected for filtering the host list by user. */
  selectedHostGroups: string[] = [];

  /** Run targets that are selected for filtering the host list by user. */
  selectedRunTargets: string[] = [];

  /** Test Harness that is selected for filtering the host list by user. */
  selectedTestHarness = '';

  lastCheckInHours = 0;
  lastCheckInOperator = TimeFilterOperator.ALL;
  lastCheckInTimestamp?: Date;

  /** Labs that owned by current user. */
  labs: LabInfo[] = [];

  /** Host groups with offline hosts. */
  hostGroups: string[] = [];

  /** Run targets of offline devices. */
  runTargets: string[] = [];

  /** Test Harnesses of offline hosts. */
  testHarnesses: string[] = [];

  /** Hosts that include offline hosts and hosts with offline devices. */
  offlineHosts: LabHostInfo[] = [];

  protected isLoadingInternal = false;
  /** Whether the data is loading. */
  set isLoading(value: boolean) {
    this.isLoadingInternal = value;
  }

  get isLoading() {
    return this.isLoadingInternal;
  }

  readonly defaultFilterParams: OfflineHostFilterParams = {
    lab: '',
    hostGroups: [],
    runTargets: [],
    testHarness: '',
    lastCheckInOperator: '',
    lastCheckInHours: 0,
  };

  totalOfflineDevicesHighlightRatio = 0.4;
  totalDeviceCountSummary: TotalDeviceCountSummary = {
    offlineDevices: 0,
    allDevices: 0,
  };

  /** An object to store the parameters parsed from URL. */
  urlParams: OfflineHostFilterParams = this.defaultFilterParams;

  /** An observable that gets the query parameters from the URL. */
  protected readonly urlQueryParamObservable: Observable<ParamMap>;

  /** An observable that gets all async initial data for Offline Hosts page. */
  protected readonly initialDataObservable: Observable<LabHostInfo[]>;

  /**
   * An observable that gets my labs from backend and selects a lab by
   * default. Users need to set owners in lab configs in advance. For admins,
   * return all labs instead.
   */
  protected readonly labsObservable: Observable<string>;

  readonly FILTER_CRITERIA_STORAGE_KEY = 'OFFLINE_HOST_LIST_FILTER_CRITERIA';
  readonly LAB_FIELD = 'lab';
  readonly RUN_TARGETS_FIELD = 'runTargets';
  readonly HOST_GROUPS_FIELD = 'hostGroups';
  readonly TEST_HARNESS_FIELD = 'testHarness';
  readonly lastCheckInOperatorField = 'lastCheckInOperator';
  readonly lastCheckInHoursField = 'lastCheckInHours';

  constructor(
      protected readonly router: Router,
      protected readonly tfcClient: TfcClient,
      protected readonly notifier: Notifier,
      protected readonly liveAnnouncer: LiveAnnouncer,
      protected readonly route: ActivatedRoute,
      protected readonly location: Location,
      protected readonly serializer: UrlSerializer,
      readonly userService: UserService,
  ) {
    this.urlQueryParamObservable = this.route.queryParamMap.pipe(take(1));
    this.initialDataObservable = this.urlQueryParamObservable.pipe(
        this.initParamsAndLab(),
        switchMap(() => this.offlineHostsObservable()),
        takeUntil(this.destroy),
        finalize(() => {
          this.isLoading = false;
        }),
    );
    this.labsObservable =
        this.tfcClient.getMyLabInfos(this.userService.isAdmin)
            .pipe(map(result => {
              this.labs = result.labInfos;
              return this.getDefaultValue(
                  this.LAB_FIELD, this.labs.map(x => x.labName));
            }));
  }

  assignHostsTo(hostAssignInfo: HostAssignInfo, next: () => void) {
    if (hostAssignInfo && hostAssignInfo.hostnames.length === 0) {
      this.notifier.showError('No hosts to assign');
      return;
    }

    const hostRecoveryStateRequests = hostAssignInfo.hostnames.map(hostname => {
      return {
        hostname,
        recovery_state: RecoveryState.ASSIGNED,
        assignee: hostAssignInfo.assignee,
      } as HostRecoveryStateRequest;
    });
    this.tfcClient.batchSetHostsRecoveryStates(hostRecoveryStateRequests)
        .pipe(takeUntil(this.destroy))
        .subscribe(
            () => {
              next();
              this.notifier.showMessage(
                  `Hosts assigned to ${hostAssignInfo.assignee}`);
              this.liveAnnouncer.announce(
                  `Hosts assigned to ${hostAssignInfo.assignee}`, 'assertive');
            },
            (error) => {
              this.notifier.showError(
                  `Failed to assign hosts to ${hostAssignInfo.assignee}`);
            });
  }

  composeFilterParams(): OfflineHostFilterParams {
    const params = {
      lab: this.selectedLab,
      hostGroups: !(this.hostGroups.length === this.selectedHostGroups.length) ?
          this.selectedHostGroups :
          [ALL_OPTIONS_VALUE],
      runTargets: !(this.runTargets.length === this.selectedRunTargets.length) ?
          this.selectedRunTargets :
          [ALL_OPTIONS_VALUE],
      testHarness: this.selectedTestHarness,
      lastCheckInOperator: this.lastCheckInOperator.urlId ?
          this.lastCheckInOperator.urlId :
          ALL_OPTIONS_VALUE,
      lastCheckInHours: this.lastCheckInHours,
    } as OfflineHostFilterParams;
    return params;
  }

  /** Composes a url path based on the filter criteria. */
  composeUrl(baseUrl: string): string {
    return this.serializer.serialize(this.router.createUrlTree(
        [baseUrl], {queryParams: this.composeFilterParams()}));
  }

  /** Gets host group list from the offline host list. */
  getHostGroups(hosts: LabHostInfo[] = this.offlineHosts): string[] {
    return distinctArray<string>(
        hosts.filter((host: LabHostInfo) => host.lab_name === this.selectedLab)
            .map((host: LabHostInfo) => host.host_group));
  }

  /** Gets run target list from the offline host list. */
  getRunTargets(hosts: LabHostInfo[] = this.offlineHosts): string[] {
    return distinctArray<string>(
               hosts
                   .filter(
                       (host: LabHostInfo) =>
                           host.lab_name === this.selectedLab &&
                           host.device_count_summaries &&
                           host.device_count_summaries.length > 0)
                   .flatMap((host: LabHostInfo) => host.device_count_summaries)
                   .map((v: DeviceCountSummary) => v.run_target))
        .sort();
  }

  /** Gets test harness list from the offline host list. */
  getTestHarnesses(hosts: LabHostInfo[] = this.offlineHosts): string[] {
    return distinctArray<string>(
               hosts
                   .filter(
                       (host: LabHostInfo) =>
                           host.lab_name === this.selectedLab)
                   .map((host: LabHostInfo) => host.testHarness))
        .sort();
  }

  /**
   * Gets default value of time filter operator from url params or from local
   * storage.
   */
  getDefaultTimeFilterOperator(): TimeFilterOperator {
    const operator =
        this.urlParams[this.lastCheckInOperatorField]?.toUpperCase();
    if (operator) {
      if (operator === TimeFilterOperator.ALL.description.toUpperCase()) {
        return TimeFilterOperator.ALL;
      } else if (operator === TimeFilterOperator.GREATER_THAN.urlId) {
        return TimeFilterOperator.GREATER_THAN;
      } else if (operator === TimeFilterOperator.WITHIN.urlId) {
        return TimeFilterOperator.WITHIN;
      }
    }

    const storedOperator =
        this.loadFromLocalStorage()[this.lastCheckInOperatorField]
            ?.toUpperCase();
    if (storedOperator === TimeFilterOperator.ALL.description.toUpperCase()) {
      return TimeFilterOperator.ALL;
    } else if (storedOperator === TimeFilterOperator.GREATER_THAN.urlId) {
      return TimeFilterOperator.GREATER_THAN;
    } else if (storedOperator === TimeFilterOperator.WITHIN.urlId) {
      return TimeFilterOperator.WITHIN;
    }

    return TimeFilterOperator.ALL;
  }

  /**
   * Gets default value of number of hours for time filter input from url params
   * or from local storage.
   */
  getDefaultTimeFilterHours(): number {
    const hours = Number(this.urlParams[this.lastCheckInHoursField]);
    if (hours && hours > 0 && hours <= 99) {
      return hours;
    }
    const storedHours =
        Number(this.loadFromLocalStorage()[this.lastCheckInHoursField]);
    if (storedHours && storedHours > 0 && storedHours <= 99) {
      return storedHours;
    }
    return 0;
  }

  /**
   * Gets the default value for a filter. The value could be specified from
   * url,last selected value stored in local storage or the first value of the
   * options.
   */
  getDefaultValue(filterField: SingleValueField, options: string[]): string {
    const urlParam = this.urlParams[filterField];
    if (urlParam === ALL_OPTIONS_VALUE) {
      return urlParam;
    }

    if (options.includes(urlParam)) {
      return urlParam;
    }

    const storedParam = this.loadFromLocalStorage()[filterField];
    if (storedParam === ALL_OPTIONS_VALUE) {
      return storedParam;
    }

    if (options.includes(storedParam)) {
      return storedParam;
    }

    if (filterField === 'lab') {
      return options.length > 0 ? options[0] : '';
    }

    return ALL_OPTIONS_VALUE;
  }

  /**
   * Gets the default values for a filter. The values could be specified from
   * url,last selected values stored in local storage or all values of the
   * options.
   */
  getDefaultValues(filterField: MultipleValuesField, options: string[]):
      string[] {
    const urlParam = this.urlParams[filterField];
    if (urlParam.includes(ALL_OPTIONS_VALUE)) {
      return options;
    }

    const matchedUrlParamValues = options.filter(h => urlParam.includes(h));

    if (matchedUrlParamValues.length > 0) {
      return matchedUrlParamValues;
    }

    const storedParam = this.loadFromLocalStorage()[filterField];
    if (storedParam.includes(ALL_OPTIONS_VALUE)) {
      return options;
    }

    const matchedStoredParamValues =
        options.filter(h => storedParam.includes(h));

    if (matchedStoredParamValues.length > 0) {
      return matchedStoredParamValues;
    }

    return [ALL_OPTIONS_VALUE];
  }

  getCurrentLabOwners(): string[] {
    const currentLab =
        this.labs.find((lab) => lab.labName === this.selectedLab);
    return currentLab ? currentLab.owners : [];
  }

  /**
   * Initializes the options of host group filter and all options are selected
   * by default. If the keepOriginalSelected parameter is true, we'll only keep
   * the original options being selected.
   */
  initHostGroupSelection(keepOriginalSelected = false) {
    this.hostGroups = this.getHostGroups();
    this.selectedHostGroups = keepOriginalSelected ?
        this.selectedHostGroups.filter(
            selected => this.hostGroups.includes(selected)) :
        this.getDefaultValues(this.HOST_GROUPS_FIELD, this.hostGroups);
  }

  /** Initializes the options of run target filter. */
  initRunTargetSelection(
      keepOriginalSelected = false, hosts: LabHostInfo[] = this.offlineHosts) {
    this.runTargets = this.getRunTargets(hosts);
    this.selectedRunTargets = keepOriginalSelected ?
        this.selectedRunTargets.filter(
            selected => this.runTargets.includes(selected)) :
        this.getDefaultValues(this.RUN_TARGETS_FIELD, this.runTargets);
  }

  /** Initializes the options of test harness filter. */
  initTestHarnessSelection(keepOriginalSelected = false) {
    this.testHarnesses = this.getTestHarnesses();
    if (keepOriginalSelected) {
      if (!this.testHarnesses.includes(this.selectedTestHarness)) {
        this.selectedTestHarness = ALL_OPTIONS_VALUE;
      }
    } else {
      this.selectedTestHarness =
          this.getDefaultValue(this.TEST_HARNESS_FIELD, this.testHarnesses);
    }
  }

  /** Initializes last check in time filter and set last check in timestamp. */
  initLastCheckInSelection() {
    this.lastCheckInOperator = this.getDefaultTimeFilterOperator();
    this.lastCheckInHours = this.getDefaultTimeFilterHours();
    if (this.lastCheckInHours) {
      const date = new Date();
      date.setHours(date.getHours() - this.lastCheckInHours);
      this.lastCheckInTimestamp = date;
    }
  }

  initParamsAndLab(): OperatorFunction<ParamMap, void> {
    return pipe(
        switchMap((params: ParamMap) => {
          this.urlParams = {
            lab: params.get(this.LAB_FIELD) || this.defaultFilterParams.lab,
            hostGroups: params.getAll(this.HOST_GROUPS_FIELD) ||
                this.defaultFilterParams.hostGroups,
            runTargets: params.getAll(this.RUN_TARGETS_FIELD) ||
                this.defaultFilterParams.runTargets,
            testHarness: params.get(this.TEST_HARNESS_FIELD) ||
                this.defaultFilterParams.testHarness,
            lastCheckInOperator: params.get(this.lastCheckInOperatorField) ||
                this.defaultFilterParams.lastCheckInOperator,
            lastCheckInHours: Number(params.get(this.lastCheckInHoursField)) ||
                this.defaultFilterParams.lastCheckInHours,
          };
          this.initLastCheckInSelection();
          return observableOf(null);
        }),
        switchMap(() => this.labsObservable),
        map((selectedLab) => {
          this.selectedLab = selectedLab;
          this.currentLabOwners = this.getCurrentLabOwners();
        }),
    );
  }

  /** Loads last criteria data from local storage if exists. */
  loadFromLocalStorage(): OfflineHostFilterParams {
    const storedData =
        window.localStorage.getItem(this.FILTER_CRITERIA_STORAGE_KEY);
    return storedData ? JSON.parse(storedData) as OfflineHostFilterParams :
                        this.defaultFilterParams;
  }

  offlineHostsObservable(): Observable<LabHostInfo[]> {
    if (!this.selectedLab) {
      return observableOf([]);
    }

    return this.tfcClient
        .getOfflineHostInfos(
            this.selectedLab, this.lastCheckInTimestamp,
            this.lastCheckInOperator.urlId)
        .pipe(
            map(result => result.host_infos || []),
        );
  }

  setSelectedRunTargets(selection: string[]) {
    this.selectedRunTargets = selection;
  }

  setHostGroups(selection: string[]) {
    this.selectedHostGroups = selection;
  }

  setLastCheckInTime(timeFilterEvent: TimeFilterEvent) {
    if (timeFilterEvent.hours) {
      this.lastCheckInHours = timeFilterEvent.hours;
    }
    if (timeFilterEvent.timestamp) {
      this.lastCheckInTimestamp = timeFilterEvent.timestamp;
    }
    this.lastCheckInOperator = timeFilterEvent.filterOperator;
  }

  /** Saves last criteria data to localstorage. */
  updateLocalStorage() {
    const criteria: OfflineHostFilterParams = {
      lab: this.selectedLab,
      hostGroups: this.selectedHostGroups === this.hostGroups ?
          [ALL_OPTIONS_VALUE] :
          this.selectedHostGroups,
      runTargets: this.selectedRunTargets === this.runTargets ?
          [ALL_OPTIONS_VALUE] :
          this.selectedRunTargets,
      testHarness: this.selectedTestHarness,
      lastCheckInOperator: this.lastCheckInOperator.urlId ?
          this.lastCheckInOperator.urlId :
          ALL_OPTIONS_VALUE,
      lastCheckInHours: this.lastCheckInHours,
    };
    window.localStorage.setItem(
        this.FILTER_CRITERIA_STORAGE_KEY, JSON.stringify(criteria));
  }
}
