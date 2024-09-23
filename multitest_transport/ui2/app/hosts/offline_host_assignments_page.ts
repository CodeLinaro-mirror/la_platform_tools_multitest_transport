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
import {DOCUMENT, Location} from '@angular/common';
import {AfterViewInit, Component, ElementRef, HostListener, Inject, OnDestroy, OnInit, ViewChild} from '@angular/core';
import {Title} from '@angular/platform-browser';
import {ActivatedRoute, Router, UrlSerializer} from '@angular/router';
import {forkJoin, Observable, of as observableOf, Subject} from 'rxjs';
import {debounceTime, finalize, map, switchMap, take, takeUntil} from 'rxjs/operators';

import {APP_DATA, AppData} from '../services';
import {FeedbackService} from '../services/feedback_service';
import {SurveyTrigger} from '../services/mtt_lab_models';
import {ALL_OPTIONS_VALUE, calculateTotalDeviceCountSummary, HostAssignInfo, LabHostInfo, TotalDeviceCountSummary} from '../services/mtt_lab_models';
import {Notifier} from '../services/notifier';
import {TfcClient} from '../services/tfc_client';
import {UserService} from '../services/user_service';
import {LAB_APPLICATION_NAME} from '../shared/shared_module';
import {TimeInputFilter} from '../shared/time_input_filter';
import {assertRequiredInput} from '../shared/util';

import {AssignedMeOfflineHostList} from './assigned_me_offline_host_list';
import {AssignedOthersOfflineHostList} from './assigned_others_offline_host_list';
import {BaseOfflineHostList} from './base_offline_host_list';
import {filterHostListDataSource} from './offline_host_filter';
import {UnassignedOfflineHostList} from './unassigned_offline_host_list';

/**
 * Displays all unassigned offline hosts and the hosts that assignments to me
 * and others. An entry page for users to start the hosts and devices recovery
 * work.The hosts listed here include the offline hosts and the hosts with
 * offline devices.
 */
@Component({
  standalone: false,
  selector: 'offline-host-assignments-page',
  styleUrls: ['offline_host_assignments_page.css'],
  templateUrl: './offline_host_assignments_page.ng.html',
})
export class OfflineHostAssignmentsPage extends BaseOfflineHostList implements
    AfterViewInit, OnInit, OnDestroy {
  @ViewChild(UnassignedOfflineHostList, {static: true})
  unassignedHostList!: UnassignedOfflineHostList;
  @ViewChild(UnassignedOfflineHostList, {static: true, read: ElementRef})
  unassignedHostListEl!: ElementRef;
  @ViewChild(AssignedMeOfflineHostList, {static: true})
  assignedMeHostList!: AssignedMeOfflineHostList;
  @ViewChild(AssignedOthersOfflineHostList, {static: true})
  assignedOthersHostList!: AssignedOthersOfflineHostList;
  @ViewChild(TimeInputFilter, {static: true}) timeInputFilter!: TimeInputFilter;

  readonly allOptionsValue = ALL_OPTIONS_VALUE;
  baseUrl = 'offline_host_assignments';
  listHeaderRowTop = '35px';
  override totalOfflineDevicesHighlightRatio = 0.4;
  override totalDeviceCountSummary: TotalDeviceCountSummary = {
    offlineDevices: 0,
    allDevices: 0,
  };
  hostListRowMaxHeight = 400;
  accordionMaxWidth = 1600;

  /** Hosts that assgined to users. */
  assignedHosts: LabHostInfo[] = [];

  hostListDataSource: LabHostInfo[] = [];
  unassignedHostListDataSource: LabHostInfo[] = [];
  assignedMeHostListDataSource: LabHostInfo[] = [];
  assignedOthersHostListDataSource: LabHostInfo[] = [];

  filterTextChanged = new Subject();

  /**
   * An observable that gets all async initial data for Offline Host
   * Assignments page.
   */
  private readonly initialOfflineHostAssignmentsDataObservable:
      Observable<[LabHostInfo[], LabHostInfo[]]> =
          this.urlQueryParamObservable.pipe(
              this.initParamsAndLab(),
              switchMap(() => forkJoin([
                          this.offlineHostsObservable(),
                          this.getAssignedHosts(),
                        ])),
              takeUntil(this.destroy),
              finalize(() => {
                this.isLoading = false;
              }),
          );

  constructor(
      private readonly feedbackService: FeedbackService,
      private readonly title: Title,
      private readonly elementRef: ElementRef,
      @Inject(DOCUMENT) private readonly document: Document,
      @Inject(APP_DATA) private readonly appData: AppData,
      router: Router,
      tfcClient: TfcClient,
      notifier: Notifier,
      liveAnnouncer: LiveAnnouncer,
      route: ActivatedRoute,
      location: Location,
      serializer: UrlSerializer,
      userService: UserService,
  ) {
    super(
        router, tfcClient, notifier, liveAnnouncer, route, location, serializer,
        userService);

    this.filterTextChanged
        .pipe(
            takeUntil(this.destroy),
            debounceTime(1000),
            take(1),
            )
        .subscribe(() => {
          this.startSearchableFilterHats();
        });
  }

  assignToMe(hosts: string[]) {
    const assignInfo: HostAssignInfo = {
      hostnames: hosts,
      assignee: this.appData.userNickname || '',
    };
    this.callAssignHostsTo(assignInfo);
    this.startOfflineHostAssignmentHats();
  }

  assignTo(assignInfo: HostAssignInfo) {
    this.callAssignHostsTo(assignInfo);
    this.startOfflineHostAssignmentHats();
  }

  callAssignHostsTo(assignInfo: HostAssignInfo) {
    super.assignHostsTo(assignInfo, () => {
      this.refresh();
    });
  }

  ngAfterViewInit() {
    setTimeout(() => {
      this.setHostListRowMaxHeight();
    }, 0);
  }

  ngOnDestroy() {
    this.destroy.next();
  }

  ngOnInit() {
    assertRequiredInput(
        this.assignedMeHostList, 'assignedMeHostList',
        'OfflineHostAssignmentsPage');
    assertRequiredInput(
        this.assignedOthersHostList, 'assignedOthersHostList',
        'OfflineHostAssignmentsPage');
    assertRequiredInput(
        this.unassignedHostList, 'unassignedOfflineHostList',
        'OfflineHostAssignmentsPage');
    assertRequiredInput(
        this.unassignedHostListEl, 'unassignedHostListEl',
        'OfflineHostAssignmentsPage');
    assertRequiredInput(
        this.timeInputFilter, 'timeInputFilter', 'OfflineHostAssignmentsPage');
    this.title.setTitle(`${LAB_APPLICATION_NAME} - Offline Host Assignments`);
    this.load();
  }

  /**
   * Filters the assigned hosts and offline hosts by host group and run target
   * and then resets the data sources of all host lists.
   */
  filterHostListsDataSources() {
    this.hostListDataSource = filterHostListDataSource(
        this.offlineHosts, this.selectedHostGroups, this.selectedRunTargets,
        this.selectedTestHarness);
    this.unassignedHostListDataSource =
        this.hostListDataSource.filter(host => !host.assignee);

    const filteredAssignedHosts = filterHostListDataSource(
        this.assignedHosts, this.selectedHostGroups, this.selectedRunTargets,
        this.selectedTestHarness, false);
    this.assignedMeHostListDataSource = filteredAssignedHosts.filter(
        host => host.assignee && host.assignee === this.appData.userNickname);
    this.assignedOthersHostListDataSource = filteredAssignedHosts.filter(
        host => host.assignee && host.assignee !== this.appData.userNickname);
  }

  /**
   * Calculates the list-row max height for host lists. So users can see the
   * filter and action buttons while scrolling down.
   */
  calculateHostListRowHeight(): number {
    const listRow = this.elementRef.nativeElement.querySelector('.list-row');
    const listRowTop = listRow ? listRow.offsetTop : 0;

    const unassignedHostsListRow =
        this.unassignedHostListEl.nativeElement.querySelector('.list-row');
    const unassignedHostsListRowTop =
        unassignedHostsListRow ? unassignedHostsListRow.offsetTop : 0;

    return this.document.body.clientHeight - listRowTop -
        unassignedHostsListRowTop;
  }

  /** Gets all assigned hosts of a lab. */
  getAssignedHosts(): Observable<LabHostInfo[]> {
    if (!this.selectedLab) {
      return observableOf([]);
    }
    return this.tfcClient
        .getAssignedHostsInfos(
            this.selectedLab, this.lastCheckInTimestamp,
            this.lastCheckInOperator.urlId)
        .pipe(
            map(result => result.host_infos || []),
        );
  }

  /** Loads data for the host list and filters. */
  load() {
    this.isLoading = true;
    this.liveAnnouncer.announce('Loading', 'polite');

    this.initialOfflineHostAssignmentsDataObservable.subscribe(
        ([offlineHosts, assignedHosts]) => {
          this.offlineHosts = offlineHosts;
          this.assignedHosts = assignedHosts;
          this.initHostGroupSelection();
          this.initRunTargetSelection();
          this.initTestHarnessSelection();
          this.initLastCheckInSelection();
          this.location.replaceState(this.composeUrl(this.baseUrl));
          this.filterHostListsDataSources();
          this.totalDeviceCountSummary = calculateTotalDeviceCountSummary([
            ...this.unassignedHostListDataSource,
            ...this.assignedMeHostListDataSource,
            ...this.assignedOthersHostListDataSource
          ]);
          this.updateLocalStorage();
          this.setAccordionMaxWidth();
          this.liveAnnouncer.announce('Loading complete', 'assertive');
        },
        () => {
          this.notifier.showError('Failed to load lab and offline host list');
        },
    );
  }

  @HostListener('window:resize')
  onResize() {
    this.setHostListRowMaxHeight();
    this.setAccordionMaxWidth();
  }

  /** Loads data for the host list and does related actions. */
  reload(next: ([offlineHosts, assignedHosts]: [
           LabHostInfo[], LabHostInfo[]
         ]) => void) {
    if (this.isLoading) return;
    this.isLoading = true;
    this.liveAnnouncer.announce('Loading', 'polite');
    this.currentLabOwners = this.getCurrentLabOwners();
    forkJoin([this.offlineHostsObservable(), this.getAssignedHosts()])
        .pipe(
            takeUntil(this.destroy),
            finalize(() => {
              this.isLoading = false;
            }),
            )
        .subscribe(
            (result) => {
              next(result);
              this.liveAnnouncer.announce('Loading complete', 'assertive');
            },
            () => {
              this.notifier.showError('Failed to load host lists');
            });
  }

  /**
   * Loads data when the value of host group or run target filter is changed.
   */
  reloadHosts() {
    this.location.replaceState(this.composeUrl(this.baseUrl));

    this.filterHostListsDataSources();

    this.totalDeviceCountSummary = calculateTotalDeviceCountSummary([
      ...this.unassignedHostListDataSource,
      ...this.assignedMeHostListDataSource,
      ...this.assignedOthersHostListDataSource
    ]);

    this.updateLocalStorage();

    this.liveAnnouncer.announce('Loading complete', 'assertive');
  }

  /**
   * Reloads the data of host lists and linked filters (e.g. host group,run
   * target, test harness) since these filters' options are based on the latest
   * offline Hosts data.
   */
  refresh(refreshFilters = true) {
    this.reload(([offlineHosts, assignedHosts]) => {
      this.offlineHosts = offlineHosts;
      this.assignedHosts = assignedHosts;

      if (refreshFilters) {
        this.initHostGroupSelection(true);
        this.initRunTargetSelection(true);
        this.initTestHarnessSelection(true);
      }

      this.reloadHosts();
    });
  }

  setHostListRowMaxHeight() {
    this.hostListRowMaxHeight = this.calculateHostListRowHeight();
  }

  setAccordionMaxWidth() {
    // A preserved space to prevent the scrollbar from being shown unexpectedly.
    const preservedSpace = 15;
    this.accordionMaxWidth =
        this.elementRef.nativeElement.offsetParent.clientWidth - preservedSpace;
  }

  startChangeSortHats() {
    this.feedbackService.startSurvey(SurveyTrigger.SORT_HOST_DATA);
  }

  startOfflineHostAssignmentHats() {
    this.feedbackService.startSurvey(SurveyTrigger.OFFLINE_HOST_ASSIGNMENT);
  }

  startSearchableFilterHats() {
    this.feedbackService.startSurvey(SurveyTrigger.SEARCHABLE_FILTER);
  }
}
