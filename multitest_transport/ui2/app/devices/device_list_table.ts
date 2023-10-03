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
import {Component, ElementRef, EventEmitter, HostListener, Inject, Input, OnChanges, OnDestroy, OnInit, Output, SimpleChanges, ViewChild} from '@angular/core';
import {MatSort, Sort} from '@angular/material/sort';
import {MatTable, MatTableDataSource} from '@angular/material/table';
import {Router} from '@angular/router';
import {TableColumn} from 'google3/third_party/py/multitest_transport/ui2/app/services/mtt_models';
import {Notifier} from 'google3/third_party/py/multitest_transport/ui2/app/services/notifier';
import {TableRowsSelectManager} from 'google3/third_party/py/multitest_transport/ui2/app/shared/table_rows_select';
import {assertRequiredInput} from 'google3/third_party/py/multitest_transport/ui2/app/shared/util';
import {of as observableOf, ReplaySubject, throwError} from 'rxjs';
import {catchError, filter, switchMap, takeUntil} from 'rxjs/operators';

import {APP_DATA, AppData} from '../services';
import {DEVICE_SERIAL, getDeviceSerialForDisplay, HOSTNAME, LabDeviceInfo, REMOVE_DEVICE_MESSAGE} from '../services/mtt_lab_models';
import {DeviceSerialWithDisplay, StorageService} from '../services/storage_service';
import {TfcClient} from '../services/tfc_client';
import {DeviceRecoveryStateRequest, RecoveryState, TestHarness} from '../services/tfc_models';
import {UserService} from '../services/user_service';

/**
 * A component for displaying a list of device.
 */
@Component({
  selector: 'device-list-table',
  styleUrls: ['device_list_table.css'],
  templateUrl: './device_list_table.ng.html',
})
export class DeviceListTable implements OnDestroy, OnInit, OnChanges {
  /** The device list data that is provided for the table. */
  @Input()
  set dataSource(value: LabDeviceInfo[]) {
    this.tableDataSource.data = value;
    this.tableDataSource.sort = this.matSort;
  }

  get dataSource() {
    return this.tableDataSource.data;
  }

  @Input()
  displayedColumns: string[] = [
    'device_serial',
    'run_target',
    'state',
    'last_checkin',
    'notesUpdateTime',
    'offline_reason',
    'recovery_action',
    'note',
    'sponge',
    'build_alias',
    'sdk_version',
    'battery_level',
    'actions',
  ];

  @Input() initialSelection: string[] = [];

  @Input() isLoading = false;

  @Input() isModalMode = false;

  @Input() headerRowTop = '0';

  /** When true, shows a column of checkboxes. */
  @Input() selectable = true;

  @Output() readonly selectionChange = new EventEmitter<string[]>();
  @Output() readonly deviceListChangeSort = new EventEmitter<Sort>();

  @ViewChild(MatTable, {static: true}) matTable!: MatTable<{}>;
  @ViewChild('table', {static: false, read: ElementRef}) table!: ElementRef;
  @ViewChild(TableRowsSelectManager, {static: true})
  tableRowsSelectManager!: TableRowsSelectManager;
  @ViewChild(MatSort, {static: true}) matSort!: MatSort;

  private readonly destroy = new ReplaySubject<void>();
  tableDataSource = new MatTableDataSource<LabDeviceInfo>([]);
  isTableScrolled = false;
  readonly recoveryState = RecoveryState;
  readonly testHarness = TestHarness;
  readonly getDeviceSerialForDisplay = getDeviceSerialForDisplay;
  logUrl = '';
  readonly COLUMN_DISPLAY_STORAGE_KEY = 'DEVICE_COLUMN_DISPLAY';
  columns: TableColumn[] = [
    {
      fieldName: 'device_serial',
      displayName: 'Device Serial',
      removable: false,
      show: true
    },
    {
      fieldName: 'run_target',
      displayName: 'Run Targets',
      removable: true,
      show: true
    },
    {
      fieldName: 'last_checkin',
      displayName: 'Last Check-in',
      removable: true,
      show: true
    },

    {fieldName: 'state', displayName: 'State', removable: true, show: true},
    {
      fieldName: 'notesUpdateTime',
      displayName: 'Notes Update Time',
      removable: true,
      show: true
    },
    {
      fieldName: 'notesUpdateTimestamp',
      displayName: 'Notes Update Timestamp',
      removable: true,
      show: false
    },
    {
      fieldName: 'offline_reason',
      displayName: 'Offline Reason',
      removable: true,
      show: true
    },
    {
      fieldName: 'recovery_action',
      displayName: 'Recovery Action',
      removable: true,
      show: true
    },
    {fieldName: 'note', displayName: 'Note', removable: true, show: true},
    {fieldName: 'sponge', displayName: 'Sponge', removable: true, show: true},
    {
      fieldName: 'build_alias',
      displayName: 'Build Alias',
      removable: true,
      show: true
    },
    {fieldName: 'sdk_version', displayName: 'SDK', removable: true, show: true},
    {
      fieldName: 'battery_level',
      displayName: 'Battery',
      removable: true,
      show: true
    },
    {fieldName: 'actions', displayName: 'Actions', removable: true, show: true},
  ];

  get deviceSerials() {
    return this.tableDataSource.data.map(info => info.device_serial);
  }

  get deviceSerialsWithDisplay(): DeviceSerialWithDisplay[] {
    return this.dataSource.map(
        info => ({
          serial: info.device_serial,
          serialForDisplay: this.getDeviceSerialForDisplay(info),
        }));
  }

  /** Clicks header to sort. */
  changeSort(sortInfo: Sort) {
    this.matSort.active = sortInfo.active;
    this.matSort.direction = sortInfo.direction;
    this.deviceListChangeSort.emit(sortInfo);
  }

  /** Check if table is scrolled to the right to update sticky styling. */
  checkTableScrolled() {
    const el = this.table.nativeElement;
    this.isTableScrolled = el.scrollLeft === el.scrollWidth - el.clientWidth;
  }

  constructor(
      private readonly liveAnnouncer: LiveAnnouncer,
      private readonly notifier: Notifier,
      private readonly router: Router,
      private readonly storageService: StorageService,
      private readonly tfcClient: TfcClient,
      readonly userService: UserService,
      @Inject(APP_DATA) private readonly appData: AppData,
  ) {
    if (!this.appData.isGoogle) {
      this.columns = this.columns.filter(x => x.fieldName !== 'sponge');
    } else {
      this.logUrl = appData.logUrl || '';
    }
  }

  /** Gets customized field values for sorting data on TableDataSource. */
  getSortingData(device: LabDeviceInfo, sortHeaderId: string): string|number {
    switch (sortHeaderId) {
      case 'device_serial':
        return device.device_serial || '';
      case 'run_target':
        return device.run_target || '';
      case 'build_alias':
        return device.extraInfo.build_id || '';
      case 'sdk_version':
        return device.extraInfo.sdk_version || '';
      case 'battery_level':
        return device.extraInfo.battery_level || '';
      case 'state':
        return device.state || '';
      case 'offline_reason':
        return device.note?.offline_reason || '';
      case 'recovery_action':
        return device.note?.recovery_action || '';
      case 'note':
        return device.note?.message || '';
      case 'notesUpdateTime':
        return Date.parse(device.note?.timestamp || '');
      case 'last_checkin':
        return Date.parse(device.timestamp);
      default:
        return '';
    }
  }

  /**
   * Initializes the visible columns. The previous setting stored in local
   * storage has the higher priority than the displayedColumns value specified
   * by parent component.
   */
  initColumns() {
    if (!this.loadDisplayedColumnFromLocalStorage()) {
      for (const c of this.columns) {
        c.show = this.displayedColumns.includes(c.fieldName);
      }
    }
  }

  private loadDisplayedColumnFromLocalStorage(): boolean {
    const storedData =
        window.localStorage.getItem(this.COLUMN_DISPLAY_STORAGE_KEY);

    if (!storedData) {
      return false;
    }

    const storedTableColumns = JSON.parse(storedData) as TableColumn[];

    for (const c of this.columns) {
      c.show =
          storedTableColumns.find((s) => s.fieldName === c.fieldName)?.show ??
          c.show;
    }

    this.setDisplayedColumns();
    return true;
  }

  /** Naviagte to device details page. */
  openDeviceDetails(deviceSerial: string) {
    this.storageService.deviceList = this.deviceSerialsWithDisplay;
    const url = this.getDeviceDetailsUrl(deviceSerial);
    this.router.navigateByUrl(url);
  }

  getDeviceDetailsUrl(deviceSerial: string): string {
    const url = this.router.serializeUrl(
        this.router.createUrlTree(['/devices', deviceSerial]));
    return url;
  }

  ngOnChanges(changes: SimpleChanges) {
    if (changes['dataSource']) {
      this.tableRowsSelectManager.rowIdFieldAllValues = this.deviceSerials;
      this.tableRowsSelectManager.selection.clear();
      this.tableRowsSelectManager.resetPrevClickedRowIndex();
    }
  }

  ngOnDestroy() {
    this.destroy.next();
  }

  ngOnInit() {
    assertRequiredInput(this.matTable, 'matTable', 'deviceListTable');
    assertRequiredInput(
        this.tableRowsSelectManager, 'tableRowsSelectManager',
        'deviceListTable');
    assertRequiredInput(this.matSort, 'matSort', 'deviceListTable');

    if (this.selectable) {
      this.displayedColumns.unshift('select');
      this.columns.unshift(
          {fieldName: 'select', displayName: '', removable: false, show: true});
    }

    this.tableRowsSelectManager.selectSelection(this.initialSelection);
    this.overrideDatsSourceSortRules();
    this.initColumns();
  }

  @HostListener('window:resize')
  onWindowResize() {
    this.checkTableScrolled();
  }

  overrideDatsSourceSortRules() {
    this.tableDataSource.sortingDataAccessor = this.getSortingData;

    // TODO: Make it a shared function
    // Overrides the sortData. We sort the data of tableDataSource directly to
    // get the same order as the rows on the table. It helps the rangeSelect
    // method to get correct index of the row on the table.
    this.tableDataSource.sortData =
        (data: LabDeviceInfo[], sort: MatSort): LabDeviceInfo[] => {
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
          this.tableRowsSelectManager.rowIdFieldAllValues = this.deviceSerials;

          return this.tableDataSource.data;
        };
  }

  /** Remove the device from the host. */
  removeDevice(event: Event, serial: string) {
    event.stopPropagation();
    this.notifier.confirm('', REMOVE_DEVICE_MESSAGE, 'Remove device', 'Cancel')
        .pipe(
            switchMap((result) => {
              if (!result) return observableOf(false);
              const hostname = this.tableDataSource.data
                                   .find(info => info.device_serial === serial)
                                   ?.hostname ??
                  '';
              return this.tfcClient.removeDevice(serial, hostname)
                  .pipe(
                      catchError((err) => throwError(err)),
                  );
            }),
            filter(
                isConfirmed =>
                    isConfirmed !== false),  // Remove canceled confirmation.
            takeUntil(this.destroy),
            )
        .subscribe(
            () => {
              this.tableDataSource.data = this.tableDataSource.data.filter(
                  x => x.device_serial !== serial);
              this.matTable.renderRows();
              this.tableRowsSelectManager.rowIdFieldAllValues =
                  this.deviceSerials;
              this.tableRowsSelectManager.resetSelection();
              this.notifier.showMessage('Device removed');
            },
            () => {
              this.notifier.showError(`Failed to remove device ${serial}`);
            });
  }

  toggleDisplayedColumn(columnIndex: number) {
    this.columns[columnIndex].show = !this.columns[columnIndex].show;
    this.setDisplayedColumns();
    this.updateDisplayedColumnToLocalStorage();
    setTimeout(() => {
      this.checkTableScrolled();
    });
  }

  setDisplayedColumns() {
    this.displayedColumns =
        this.columns.filter(c => c.show).map(c => c.fieldName);
  }

  updateDisplayedColumnToLocalStorage() {
    window.localStorage.setItem(
        this.COLUMN_DISPLAY_STORAGE_KEY, JSON.stringify(this.columns));
  }

  toggleDeviceFixedState(device: LabDeviceInfo, event: MouseEvent) {
    event.stopPropagation();
    if (!this.appData.userNickname) {
      this.notifier.showError('Please sign in');
      return;
    }

    const currentState = device.recovery_state;
    const fixedMsg = `The device's recovery state has been marked as FIXED`;
    const undoMsg = `The device's recovery state marked back as UNKNOWN.`;
    const errMsg = `Failed to mark the device's recovery state as FIXED`;
    const msg = currentState === RecoveryState.FIXED ? undoMsg : fixedMsg;

    const nextState = currentState === RecoveryState.FIXED ?
        RecoveryState.UNKNOWN :
        RecoveryState.FIXED;

    const deviceRecoveryStateRequests = [{
      hostname: device.hostname,
      device_serial: device.device_serial,
      recovery_state: nextState,
    } as DeviceRecoveryStateRequest];

    this.tfcClient.batchSetDevicesRecoveryStates(deviceRecoveryStateRequests)
        .pipe(takeUntil(this.destroy))
        .subscribe(
            () => {
              device.recovery_state = nextState;
              this.notifier.showMessage(msg);
              this.liveAnnouncer.announce(msg, 'assertive');
            },
            () => {
              this.notifier.showError(errMsg);
            });
  }

  getLogUrl(device: LabDeviceInfo): string {
    return this.logUrl.replace(HOSTNAME, device.hostname || '')
        .replace(DEVICE_SERIAL, device.device_serial);
  }

  storeDeviceSerialsInLocalStorage() {
    this.storageService.saveDeviceListInLocalStorage(
        this.deviceSerialsWithDisplay);
  }
}
