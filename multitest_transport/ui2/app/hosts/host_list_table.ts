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
import {Component, EventEmitter, Inject, Input, OnChanges, OnDestroy, OnInit, Output, SimpleChanges, ViewChild} from '@angular/core';
import {MatDialog} from '@angular/material/dialog';
import {MatTable, MatTableDataSource} from '@angular/material/table';
import {MatSort, Sort} from '@angular/material/sort';
import {Router} from '@angular/router';
import {ReplaySubject} from 'rxjs';
import {takeUntil} from 'rxjs/operators';

import {APP_DATA, AppData} from '../services';
import {HostAssignInfo, LabHostInfo, NavigatePageMode} from '../services/mtt_lab_models';
import {Notifier} from '../services/notifier';
import {StorageService} from '../services/storage_service';
import {TfcClient} from '../services/tfc_client';
import {HostRecoveryStateRequest, HostState, RecoveryState} from '../services/tfc_models';
import {UserService} from '../services/user_service';
import {OverflowListType} from '../shared/overflow_list';
import {TableRowsSelectManager} from '../shared/table_rows_select';
import {assertRequiredInput} from '../shared/util';

import {HostDetails, HostDetailsDialogParams} from './host_details';

/**
 * A component for displaying a list of hosts.
 */
@Component({
  selector: 'host-list-table',
  styleUrls: ['host_list_table.css'],
  templateUrl: './host_list_table.ng.html',
})
export class HostListTable implements OnInit, OnChanges, OnDestroy {
  /** The host list data that is provided for the table. */
  @Input()
  set dataSource(value: LabHostInfo[]) {
    this.tableDataSource.data = value;
    this.tableDataSource.sort = this.matSort;
  }

  get dataSource() {
    return this.tableDataSource.data;
  }

  @Input()
  displayedColumns: string[] = [
    'hostname',
    'host_group',
    'host_state',
    'run_target',
    'offline_devices',
    'last_checkin',
    'lastRecoveryTime',
    'testHarness',
    'assignee',
    'recoveryState',
    'actions',
  ];

  @Input() isLoading = false;

  @Input() initialSelection: string[] = [];

  @Input() headerRowTop = '0';

  /** When true, shows a column of checkboxes. */
  @Input() selectable = true;

  @Input() navigatePageMode: NavigatePageMode = NavigatePageMode.PAGE;

  @Output() readonly selectionChange = new EventEmitter<string[]>();
  @Output() readonly hostAssigneeChange = new EventEmitter<HostAssignInfo>();
  @Output() readonly hostListChangeSort = new EventEmitter<Sort>();
  @Output() readonly removeHostFromList = new EventEmitter<LabHostInfo>();

  @ViewChild(MatTable, {static: true}) matTable!: MatTable<{}>;

  private readonly destroy = new ReplaySubject<void>();

  tableDataSource = new MatTableDataSource<LabHostInfo>([]);

  readonly OverflowListType = OverflowListType;
  readonly RecoveryState = RecoveryState;
  readonly hostnameStorageKey = 'HOSTNAME_' + new Date().getTime().toString();

  get hostnames() {
    return this.tableDataSource.data.map(x => x.hostname);
  }

  @ViewChild(MatSort, {static: true}) matSort!: MatSort;

  @ViewChild(TableRowsSelectManager, {static: true})
  tableRowsSelectManager!: TableRowsSelectManager;

  constructor(
      public dialog: MatDialog,
      private readonly router: Router,
      @Inject(APP_DATA) private readonly appData: AppData,
      private readonly notifier: Notifier,
      private readonly liveAnnouncer: LiveAnnouncer,
      private readonly storageService: StorageService,
      private readonly tfcClient: TfcClient,
      readonly userService: UserService,
  ) {}

  ngOnInit() {
    assertRequiredInput(this.matSort, 'matSort', 'hostListTable');
    assertRequiredInput(this.matTable, 'matTable', 'hostListTable');
    assertRequiredInput(
        this.tableRowsSelectManager, 'tableRowsSelectManager', 'hostListTable');

    if (this.selectable) {
      this.displayedColumns.unshift('select');
    }

    this.tableRowsSelectManager.selectSelection(this.initialSelection);

    this.overrideDatsSourceSortRules();
  }

  ngOnChanges(changes: SimpleChanges) {
    if (changes['dataSource']) {
      // Uses setTimeout here to prevent
      // ExpressionChangedAfterItHasBeenCheckedError when
      // dataSource is updated from the parent component
      // asynchronously.
      setTimeout(() => {
        this.tableRowsSelectManager.rowIdFieldAllValues = this.hostnames;
        this.tableRowsSelectManager.resetSelection();
      });
    }
  }

  ngOnDestroy() {
    this.destroy.next();
  }

  /** Naviagtes to host details page. */
  openHostDetails(hostName: string, event: Event) {
    const hostnames = this.dataSource.map(x => x.hostname);
    this.storageService.hostList = hostnames;

    if (this.navigatePageMode === NavigatePageMode.PAGE) {
      const url = this.getHostDetailsUrl(hostName);
      this.router.navigateByUrl(url);
    } else {
      event.stopPropagation();
      const data: HostDetailsDialogParams = {id: hostName, newWindow: true};
      this.dialog.open(HostDetails, {
        height: '850px',
        width: '1400px',
        panelClass: 'host-details-container',
        data,
      });
    }
  }

  getHostDetailsUrl(hostName: string) {
    const url = this.router.serializeUrl(
        this.router.createUrlTree(['/hosts', hostName]));
    return url;
  }

  storeHostNamesInLocalStorage() {
    const hostnames = this.dataSource.map(x => x.hostname);
    this.storageService.saveHostListInLocalStorage(hostnames);
  }

  /** Gets run targets from the dataSource. */
  getRunTargets(host: LabHostInfo): string[] {
    return host.device_count_summaries ?
        host.device_count_summaries.map(x => x.run_target) :
        [];
  }

  /** Clicks header to sort. */
  changeSort(sortInfo: Sort) {
    this.matSort.active = sortInfo.active;
    this.matSort.direction = sortInfo.direction;
    this.hostListChangeSort.emit(sortInfo);
  }

  /**
   * Gets a mat-icon name to use in Offline Devices column.
   * We use the 'error' icon here with yellow color and the 'warning' icon with
   * red color.
   */
  getOfflineDevicesAlertIcon(host: LabHostInfo): string {
    const disabled = 'disabled';
    if (!host.extraInfo) {
      return disabled;
    }
    const totalDevices = Number(host.extraInfo.total_devices) ?? 0;
    const offlineDevices = Number(host.extraInfo.offline_devices) ?? 0;
    if (offlineDevices === 0 && totalDevices >= 0) {
      return disabled;
    } else if (
        host.host_state !== HostState.GONE && offlineDevices > 0 &&
        totalDevices > 0 && offlineDevices === totalDevices) {
      return 'warning';
    }

    return 'error';
  }

  /**
   * Gets a mat-icon name to represent overall host state including devices of
   * the host. We use the 'warning' icon with red color here.
   */
  getHostOverallAlertIcon(host: LabHostInfo): string {
    const offlineDevices = Number(host.extraInfo?.offline_devices) ?? 0;
    if (offlineDevices === 0 && host.host_state !== HostState.GONE) {
      return 'disabled';
    }
    return 'warning';
  }

  overrideDatsSourceSortRules() {
    this.tableDataSource.sortingDataAccessor = this.getSortingData;

    // TODO: Make it a shared function
    // Overrides the sortData. We sort the data of tableDataSource directly to
    // get the same order as the rows on the table. It helps the rangeSelect
    // method to get correct index of the row on the table.
    this.tableDataSource.sortData =
        (data: LabHostInfo[], sort: MatSort): LabHostInfo[] => {
          const {active, direction} = sort;
          if (!active || direction === '') {
            return data;
          }

          this.tableDataSource.data.sort((rowA, rowB) => {
            const valueA =
                this.tableDataSource.sortingDataAccessor(rowA, active);
            const valueB =
                this.tableDataSource.sortingDataAccessor(rowB, active);

            let comparatorResult = 0;
            if (valueA != null && valueB != null) {
              if (valueA > valueB) {
                comparatorResult = 1;
              } else if (valueA < valueB) {
                comparatorResult = -1;
              }
            } else if (valueA != null) {
              comparatorResult = 1;
            } else if (valueB != null) {
              comparatorResult = -1;
            }

            return comparatorResult * (direction === 'asc' ? 1 : -1);
          });

          this.tableRowsSelectManager.resetPrevClickedRowIndex();
          this.tableRowsSelectManager.rowIdFieldAllValues = this.hostnames;

          return this.tableDataSource.data;
        };
  }

  /** Gets customized field values for sorting data on TableDataSource. */
  getSortingData(host: LabHostInfo, sortHeaderId: string): string|number {
    switch (sortHeaderId) {
      case 'hostname':
        return host.hostname || '';
      case 'host_group':
        return host.host_group || '';
      case 'host_state':
        return host.host_state || '';
      case 'testHarness':
        return host.testHarness || '';
      case 'assignee':
        return host.assignee || '';
      case 'lastRecoveryTime':
        return Date.parse(host.lastRecoveryTime);
      case 'last_checkin':
        return Date.parse(host.timestamp);
      case 'hostOverallState':
        return this.getHostOverallAlertIcon(host);
      case 'recoveryState':
        return host.recoveryState || '';
      default:
        return '';
    }
  }

  toggleHostFixedState(host: LabHostInfo, event: MouseEvent) {
    event.stopPropagation();
    if (!this.appData.userNickname) {
      this.notifier.showError('Please sign in');
      return;
    }

    const currentState = host.recoveryState;
    const fixedMsg = 'The host has been marked as fixed';
    const undoMsg = 'The fixed state has been undone.';
    const errMsg = 'Failed to mark the host as fixed';
    const msg = currentState === RecoveryState.FIXED ? undoMsg : fixedMsg;

    const nextState = currentState === RecoveryState.FIXED ?
        RecoveryState.ASSIGNED :
        RecoveryState.FIXED;

    const hostRecoveryStateRequests = [{
      hostname: host.hostname,
      recovery_state: nextState,
      assignee: this.appData.userNickname
    } as HostRecoveryStateRequest];

    this.tfcClient.batchSetHostsRecoveryStates(hostRecoveryStateRequests)
        .pipe(takeUntil(this.destroy))
        .subscribe(
            () => {
              this.notifier.showMessage(msg);
              this.removeHostFromList.emit(host);
              this.liveAnnouncer.announce(msg, 'assertive');
            },
            () => {
              this.notifier.showError(errMsg);
            });
  }
}
