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

import {DebugElement, SimpleChange} from '@angular/core';
import {ComponentFixture, fakeAsync, TestBed, tick} from '@angular/core/testing';
import {SortDirection} from '@angular/material/sort';
import {NoopAnimationsModule} from '@angular/platform-browser/animations';
import {Router} from '@angular/router';
import {getEl, getTextContent} from 'google3/third_party/py/multitest_transport/ui2/app/testing/jasmine_util';
import {of as observableOf} from 'rxjs';

import {APP_DATA} from '../services';
import {DEVICE_SERIAL, HOSTNAME, LabDeviceInfo} from '../services/mtt_lab_models';
import {Notifier} from '../services/notifier';
import {DEVICE_LIST_KEY} from '../services/storage_service';
import {TfcClient} from '../services/tfc_client';
import {DeviceRecoveryStateRequest, RecoveryState} from '../services/tfc_models';
import {newMockAppData, newMockLabDeviceInfo, newMockLabDeviceInfosResponse} from '../testing/mtt_lab_mocks';

import {DeviceListTable} from './device_list_table';
import {DevicesModule} from './devices_module';

describe('DeviceListTable', () => {
  let deviceListTable: DeviceListTable;
  let deviceListTableFixture: ComponentFixture<DeviceListTable>;
  let el: DebugElement;
  let mockDeviceList: LabDeviceInfo[];
  let tfcClientSpy: jasmine.SpyObj<TfcClient>;
  let notifierSpy: jasmine.SpyObj<Notifier>;
  let routerSpy: jasmine.SpyObj<Router>;

  beforeEach(() => {
    const hostname = 'host01';
    const hostInfo = newMockLabDeviceInfosResponse(hostname);
    mockDeviceList = hostInfo.deviceInfos!;

    tfcClientSpy = jasmine.createSpyObj('tfcClient', {
      removeDevice: observableOf(undefined),
      batchSetDevicesRecoveryStates: observableOf(undefined)
    });

    routerSpy = jasmine.createSpyObj('Router', {
      createUrlTree: Promise.resolve(true),
      navigate: Promise.resolve(true),
      navigateByUrl: Promise.resolve(true),
      serializeUrl: Promise.resolve(true),
    });

    notifierSpy = jasmine.createSpyObj('notifier', {
      confirm: observableOf(true),  // mock confirm click in dialog.
      showMessage: observableOf({}),
      showError: observableOf({}),
    });

    window.localStorage.clear();

    TestBed.configureTestingModule({
      imports: [
        DevicesModule,
        NoopAnimationsModule,
      ],
      providers: [
        {provide: APP_DATA, useValue: newMockAppData()},
        {provide: Notifier, useValue: notifierSpy},
        {provide: Router, useValue: routerSpy},
        {provide: TfcClient, useValue: tfcClientSpy},
      ],
    });

    deviceListTableFixture = TestBed.createComponent(DeviceListTable);
    el = deviceListTableFixture.debugElement;
    deviceListTable = deviceListTableFixture.componentInstance;
    deviceListTableFixture.detectChanges();
  });

  it('initializes a component', () => {
    expect(deviceListTable).toBeTruthy();
  });

  it('shows aria-label correctly', () => {
    const checkbox = getEl(el, 'mat-checkbox input');
    expect(checkbox).toBeTruthy();
    expect(checkbox.getAttribute('aria-label')).toBe('Select all devices');
  });

  it('correctly displays a given empty list', () => {
    deviceListTable.dataSource = [];
    deviceListTableFixture.detectChanges();
    expect(getTextContent(el)).toContain('No devices found.');
  });

  it('correctly displays a given device list', () => {
    deviceListTable.dataSource = mockDeviceList;
    deviceListTableFixture.detectChanges();
    expect(getTextContent(el)).toContain(mockDeviceList[0].device_serial);
  });

  it('displays "-" when the battery level is unknown', () => {
    const device = mockDeviceList[0];
    device.extraInfo.battery_level = -0.01;
    deviceListTable.dataSource = [device];
    deviceListTableFixture.detectChanges();
    const batteryCell = getEl(el, 'mat-cell.mat-column-battery_level');
    expect(batteryCell.textContent!.trim()).toEqual('-');
  });

  it('displays the battery level as a percentage', () => {
    const device = mockDeviceList[0];
    device.extraInfo.battery_level = 0.34;
    deviceListTable.dataSource = [device];
    deviceListTableFixture.detectChanges();
    const batteryCell = getEl(el, 'mat-cell.mat-column-battery_level');
    expect(batteryCell.textContent!.trim()).toEqual('34%');
  });

  it('displays correct aria label for table', () => {
    const matTable = getEl(el, 'mat-table');
    expect(matTable).toBeTruthy();
    expect(matTable.getAttribute('aria-label')).toBe('Device list');
  });

  it('should remove device correctly', () => {
    const mockClickEvent = new MouseEvent('click');
    const serial = mockDeviceList[0].device_serial;
    deviceListTable.dataSource = mockDeviceList;
    deviceListTableFixture.detectChanges();
    deviceListTable.removeDevice(mockClickEvent, serial);

    expect(tfcClientSpy.removeDevice)
//TODO: Wait until b/208710526 is fixed, then remove this autogenerated error suppression.
// @ts-ignore(go/unfork-jasmine-typings): Argument of type 'string | undefined' is not assignable to parameter of type 'Expected<string>'.
        .toHaveBeenCalledWith(serial, mockDeviceList[0].hostname);
    expect(tfcClientSpy.removeDevice).toHaveBeenCalledTimes(1);
  });

  it('should show or hide column correctly when calling toggleDisplayedColumn',
     () => {
       const colIndex = deviceListTable.columns.findIndex(c => c.removable);
       const expectShow = !deviceListTable.columns[colIndex].show;

       deviceListTable.toggleDisplayedColumn(colIndex);

       expect(deviceListTable.displayedColumns.includes(
                  deviceListTable.columns[colIndex].fieldName))
           .toEqual(expectShow);
     });

  it('should show columns correctly when calling initColumns', () => {
    deviceListTable.displayedColumns = [
      'notesUpdateTime',
      'offline_reason',
      'recovery_action',
      'note',
    ];
    deviceListTable.initColumns();
    const stateCol =
        deviceListTable.columns.find(x => x.fieldName === 'state')!;
    const actionsCol =
        deviceListTable.columns.find(x => x.fieldName === 'actions')!;
    const offlineReasonCol =
        deviceListTable.columns.find(x => x.fieldName === 'offline_reason')!;
    expect(stateCol.show).toBeFalse();
    expect(actionsCol.show).toBeFalse();
    expect(offlineReasonCol.show).toBeTrue();

    deviceListTable.setDisplayedColumns();
    deviceListTable.updateDisplayedColumnToLocalStorage();
    deviceListTable.displayedColumns = [
      'device_serial',
      'notesUpdateTime',
      'recovery_action',
      'note',
    ];
    deviceListTable.initColumns();
    const deviceSerialCol =
        deviceListTable.columns.find(x => x.fieldName === 'device_serial')!;
    expect(offlineReasonCol.show).toBeTrue();
    expect(deviceSerialCol.show).toBeFalse();
  });

  it('gets sorting data correctly', () => {
    const device = mockDeviceList[0];
    expect(deviceListTable.getSortingData(device, 'last_checkin'))
        .toEqual(Date.parse(device.timestamp));
    expect(deviceListTable.getSortingData(device, 'notesUpdateTime'))
        .toEqual(Date.parse(device.note?.timestamp || ''));
    expect(deviceListTable.getSortingData(device, 'device_serial'))
        .toEqual(device.device_serial);
    expect(deviceListTable.getSortingData(device, 'state'))
        .toEqual(device.state);
    expect(deviceListTable.getSortingData(device, 'run_target'))
        .toEqual(device.run_target || '');
    expect(deviceListTable.getSortingData(device, 'build_alias'))
        .toEqual(device.extraInfo.build_id || '');
    expect(deviceListTable.getSortingData(device, 'sdk_version'))
        .toEqual(device.extraInfo.sdk_version);
    expect(deviceListTable.getSortingData(device, 'battery_level'))
        .toEqual(device.extraInfo.battery_level);
    expect(deviceListTable.getSortingData(device, 'offline_reason'))
        .toEqual(device.note?.offline_reason || '');
    expect(deviceListTable.getSortingData(device, 'recovery_action'))
        .toEqual(device.note?.recovery_action || '');
    expect(deviceListTable.getSortingData(device, 'note'))
        .toEqual(device.note?.message || '');
    expect(deviceListTable.getSortingData(device, 'others')).toEqual('');
  });

  it('can sort correctly', () => {
    const sortColumn = 'notesUpdateTime';
    const sortDirection: SortDirection = 'desc';
    const sort = {active: sortColumn, direction: sortDirection};
    deviceListTable.changeSort(sort);
    expect(deviceListTable.matSort.active).toEqual(sortColumn);
    expect(deviceListTable.matSort.direction).toEqual(sortDirection);
  });

  it(`resets the order of rowIdFieldAllValues correctly after sorting the 
     device_serial`,
     fakeAsync(() => {
       spyOn(
           deviceListTable.tableRowsSelectManager, 'resetPrevClickedRowIndex');
       const expectedRowIdFieldAllValues = [
         'device1', 'device10', 'device11', 'device12', 'device2', 'device3',
         'device4', 'device5', 'device6', 'device7', 'device8', 'device9'
       ];
       deviceListTable.dataSource = mockDeviceList;
       deviceListTable.ngOnChanges(
           {dataSource: new SimpleChange(null, mockDeviceList, true)});
       deviceListTableFixture.detectChanges();
       tick();
       expect(deviceListTable.tableRowsSelectManager.resetPrevClickedRowIndex)
           .toHaveBeenCalledTimes(1);

       const sortColumn = 'device_serial';
       const sortDirection: SortDirection = 'asc';
       deviceListTable.matSort.active = sortColumn;
       deviceListTable.matSort.direction = sortDirection;

       deviceListTable.tableDataSource.sortData(
           deviceListTable.tableDataSource.data, deviceListTable.matSort);

       expect(deviceListTable.tableRowsSelectManager.rowIdFieldAllValues)
           .toEqual(expectedRowIdFieldAllValues);
       expect(deviceListTable.tableRowsSelectManager.resetPrevClickedRowIndex)
           .toHaveBeenCalledTimes(2);
     }));

  it('navigates correctly when calling openDeviceDetails', () => {
    const deviceSerial = mockDeviceList[0].device_serial;
    deviceListTable.dataSource = mockDeviceList;
    deviceListTable.openDeviceDetails(deviceSerial);
    expect(routerSpy.createUrlTree).toHaveBeenCalledWith([
      '/devices', deviceSerial
    ]);
    expect(routerSpy.navigateByUrl).toHaveBeenCalledTimes(1);
  });

  it('call tfcClient correctly when calling toggleDeviceFixedState', () => {
    const device = mockDeviceList[0];
    const mouseEvent = new MouseEvent('click');
    const deviceRecoveryStateRequests = [{
      hostname: device.hostname,
      device_serial: device.device_serial,
      recovery_state: RecoveryState.FIXED,
    } as DeviceRecoveryStateRequest];
    deviceListTable.toggleDeviceFixedState(device, mouseEvent);
    expect(tfcClientSpy.batchSetDevicesRecoveryStates).toHaveBeenCalledTimes(1);
    expect(tfcClientSpy.batchSetDevicesRecoveryStates)
        .toHaveBeenCalledWith(deviceRecoveryStateRequests);
  });

  it('calls getLogUrl and returns correctly', () => {
    const url = `http://server01/hostname:${HOSTNAME}%20s%2F${DEVICE_SERIAL}`;
    deviceListTable.logUrl = url;
    const device = 'device01';
    const deviceInfo = newMockLabDeviceInfo(device);
    const logUrl = deviceListTable.getLogUrl(deviceInfo);
    expect(logUrl).toEqual(
        url.replace(HOSTNAME, deviceInfo.hostname || '')
            .replace(DEVICE_SERIAL, deviceInfo.device_serial));
  });

  it('should store device serial list in local storage correctly', () => {
    deviceListTable.storeDeviceSerialsInLocalStorage();
    const data = window.localStorage.getItem(DEVICE_LIST_KEY);
    expect(data).toBeDefined();

    const deviceSerials = JSON.parse(data!) as string[];
    expect(deviceSerials.length)
        .toEqual(deviceListTable.dataSource.map(x => x.device_serial).length);
  });
});
