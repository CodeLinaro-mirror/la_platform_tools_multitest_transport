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
import {Component, Inject, OnDestroy, OnInit, ViewChild, ChangeDetectionStrategy} from '@angular/core';
import {ActivatedRoute, Router, UrlSerializer} from '@angular/router';
import {finalize, takeUntil} from 'rxjs/operators';

import {APP_DATA, AppData} from '../services';
import {ALL_OPTIONS_VALUE, calculateTotalDeviceCountSummary, LabHostInfo, NavigatePageMode} from '../services/mtt_lab_models';
import {Notifier} from '../services/notifier';
import {TfcClient} from '../services/tfc_client';
import {HostRecoveryStateRequest, RecoveryState} from '../services/tfc_models';
import {UserService} from '../services/user_service';
import {TimeInputFilter} from '../shared';
import {assertRequiredInput} from '../shared/util';

import {BaseOfflineHostList} from './base_offline_host_list';
import {HostListTable} from './host_list_table';
import {filterHostListDataSource} from './offline_host_filter';

/** Displays offline hosts or hosts with offline devices. */
@Component({
  changeDetection: ChangeDetectionStrategy.Eager,standalone: false,
  selector: 'offline-host-list',
  styleUrls: ['offline_host_list.css'],
  templateUrl: './offline_host_list.ng.html',
})
export class OfflineHostList extends BaseOfflineHostList implements OnInit,
                                                                    OnDestroy {
  @ViewChild(HostListTable, {static: true}) hostList!: HostListTable;
  @ViewChild(TimeInputFilter, {static: true}) timeInputFilter!: TimeInputFilter;

  /**
   * Hosts that is provided as the data source of host list. It's the data could
   * be filtered out by run target filter.
   */
  hostListDataSource: LabHostInfo[] = [];

  /** Whether the data is loading. */
  override set isLoading(value: boolean) {
    this.isLoadingInternal = value;
    this.hostList.isLoading = value;
  }

  readonly allOptionsValue = ALL_OPTIONS_VALUE;
  listHeaderRowTop = '35px';
  baseUrl = 'offline_hosts';
  listTableNavigatePageMode = NavigatePageMode.DIALOG;
  constructor(
      router: Router,
      tfcClient: TfcClient,
      notifier: Notifier,
      liveAnnouncer: LiveAnnouncer,
      route: ActivatedRoute,
      location: Location,
      serializer: UrlSerializer,
      userService: UserService,
      @Inject(APP_DATA) private readonly appData: AppData,
  ) {
    super(
        router, tfcClient, notifier, liveAnnouncer, route, location, serializer,
        userService);
  }

  ngOnInit() {
    assertRequiredInput(this.hostList, 'hostList', 'offlineHostList');
    assertRequiredInput(
        this.timeInputFilter, 'timeInputFilter', 'timeInputFilter');
    this.load();
  }

  ngOnDestroy() {
    this.destroy.next();
  }

  /** Loads data for the host list and filters. */
  load() {
    this.isLoading = true;
    this.liveAnnouncer.announce('Loading', 'polite');

    this.initialDataObservable.subscribe(
        (result) => {
          this.offlineHosts = result;
          this.initHostGroupSelection();
          this.initRunTargetSelection();
          this.initTestHarnessSelection();
          this.location.replaceState(this.composeUrl(this.baseUrl));

          this.hostListDataSource = filterHostListDataSource(
              this.offlineHosts, this.selectedHostGroups,
              this.selectedRunTargets, this.selectedTestHarness);

          this.totalDeviceCountSummary =
              calculateTotalDeviceCountSummary(this.offlineHosts);
          this.updateLocalStorage();
          this.liveAnnouncer.announce('Loading complete', 'assertive');
        },
        () => {
          this.notifier.showError('Failed to load lab and offline host list');
        },
    );
  }

  /** Marks selected hosts as in recover and redirect to recovery page. */
  startRecovering() {
    if (this.hostList.tableRowsSelectManager.selection.selected.length > 0) {
      const hostRecoveryStateRequests =
          this.hostList.tableRowsSelectManager.selection.selected.map(
              hostname => {
                return {
                  hostname,
                  recovery_state: RecoveryState.ASSIGNED,
                  assignee: this.appData.userNickname || '',
                } as HostRecoveryStateRequest;
              });
      this.tfcClient.batchSetHostsRecoveryStates(hostRecoveryStateRequests)
          .subscribe(
              (result) => {
                this.navigateToRecoveryPage();
              },
              (error) => {
                this.notifier.showError('Failed to mark hosts as recovering');
              });
    } else {
      this.navigateToRecoveryPage();
    }
  }

  /**
   * Reloads the data of host list.
   * @param refreshFilters if ture reload options in filter.
   */
  refresh(refreshFilters = true) {
    this.reload((result: LabHostInfo[]) => {
      // Gets offline hosts by lab criterion from the backend
      this.offlineHosts = result || [];

      if (refreshFilters) {
        // Refreshes the options of filters based on offlineHosts
        this.hostGroups = this.getHostGroups();
        this.runTargets = this.getRunTargets();
        this.testHarnesses = this.getTestHarnesses();

        // Keeps the options of filters selected if exist.
        this.selectedHostGroups = this.selectedHostGroups.filter(
            selected => this.hostGroups.includes(selected));

        this.selectedRunTargets = this.selectedRunTargets.filter(
            selected => this.runTargets.includes(selected));

        if (!this.testHarnesses.includes(this.selectedTestHarness)) {
          this.selectedTestHarness = ALL_OPTIONS_VALUE;
        }
      }

      this.reloadHosts();
    });
  }

  /** Loads data for the host list and does related actions. */
  reload(next: (value: LabHostInfo[]) => void) {
    if (this.isLoading) return;
    this.isLoading = true;
    this.liveAnnouncer.announce('Loading', 'polite');
    this.currentLabOwners = this.getCurrentLabOwners();
    this.offlineHostsObservable()
        .pipe(
            takeUntil(this.destroy),
            finalize(() => {
              this.isLoading = false;
            }),
            )
        .subscribe(next, () => {
          this.notifier.showError('Failed to load offline host list');
        });
  }

  /**
   * Loads data when the value of host group or run target filter is changed.
   */
  reloadHosts() {
    this.location.replaceState(this.composeUrl(this.baseUrl));

    // Filters offline hosts by host group and run target and resets the data
    // source of host list.
    this.hostListDataSource = filterHostListDataSource(
        this.offlineHosts, this.selectedHostGroups, this.selectedRunTargets,
        this.selectedTestHarness);

    this.totalDeviceCountSummary =
        calculateTotalDeviceCountSummary(this.offlineHosts);

    // Keeps the selected hosts only if the hosts exist in host list.
    this.hostList.tableRowsSelectManager.resetSelection();

    this.updateLocalStorage();
  }

  /** Loads data when the value of lab filter is changed. */
  reloadHostsAndFilters() {
    this.reload((result: LabHostInfo[]) => {
      // Gets offline hosts by lab criterion from the backend
      this.offlineHosts = result || [];

      this.hostGroups = this.getHostGroups();
      this.selectedHostGroups = [ALL_OPTIONS_VALUE];

      // Refreshes the options of filters based on offlineHosts
      this.runTargets = this.getRunTargets();
      this.selectedRunTargets = [ALL_OPTIONS_VALUE];

      this.testHarnesses = this.getTestHarnesses();

      if (!this.testHarnesses.includes(this.selectedTestHarness)) {
        this.selectedTestHarness = ALL_OPTIONS_VALUE;
      }

      this.location.replaceState(this.composeUrl(this.baseUrl));

      this.updateLocalStorage();

      // Filters offline hosts by Run Target and resets data source.
      this.hostListDataSource = filterHostListDataSource(
          this.offlineHosts, this.selectedHostGroups, this.selectedRunTargets,
          this.selectedTestHarness);

      this.totalDeviceCountSummary =
          calculateTotalDeviceCountSummary(this.offlineHosts);

      this.liveAnnouncer.announce('Loading complete', 'assertive');
    });
  }

  /**
   * Navigates to recovery page and pass current filter criteria as parameters.
   */
  navigateToRecoveryPage() {
    this.router.navigate(
        ['/recovery'], {queryParams: this.composeFilterParams()});
  }
}
