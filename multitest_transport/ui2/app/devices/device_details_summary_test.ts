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

import {DebugElement} from '@angular/core';
import {ComponentFixture, TestBed} from '@angular/core/testing';
import {NoopAnimationsModule} from '@angular/platform-browser/animations';
import {provideRouter} from '@angular/router';
import {getTextContent} from 'google3/third_party/py/multitest_transport/ui2/app/testing/jasmine_util';
import {of as observableOf, throwError} from 'rxjs';

import {APP_DATA} from '../services';
import {DEVICE_SERIAL, HOSTNAME} from '../services/mtt_lab_models';
import {Notifier} from '../services/notifier';
import {TfcClient} from '../services/tfc_client';
import {newMockAppData, newMockLabDeviceInfo} from '../testing/mtt_lab_mocks';

import {DeviceDetailsSummary} from './device_details_summary';
import {DevicesModule} from './devices_module';

describe('DeviceDetailsSummary', () => {
  let deviceDetailsSummary: DeviceDetailsSummary;
  let deviceDetailsSummaryFixture: ComponentFixture<DeviceDetailsSummary>;
  let tfcClient: jasmine.SpyObj<TfcClient>;
  let notifierSpy: jasmine.SpyObj<Notifier>;
  let el: DebugElement;

  const serial = 'device1';
  const hostname = 'host01';
  const mockDeviceInfo = newMockLabDeviceInfo(serial);

  beforeEach(() => {
    tfcClient = jasmine.createSpyObj('tfcClient', {
      getDeviceInfo: observableOf(mockDeviceInfo),
      removeDevice: observableOf({}),
    });

    notifierSpy = jasmine.createSpyObj('notifier', {
      confirm: observableOf(true),  // mock confirm click in dialog.
      showMessage: observableOf({}),
      showError: observableOf({}),
    });

    TestBed.configureTestingModule({
      imports: [
        DevicesModule,
        NoopAnimationsModule,
      ],
      providers: [
        provideRouter([]),
        {provide: APP_DATA, useValue: newMockAppData()},
        {provide: Notifier, useValue: notifierSpy},
        {provide: TfcClient, useValue: tfcClient},
      ],
    });

    deviceDetailsSummaryFixture = TestBed.createComponent(DeviceDetailsSummary);
    el = deviceDetailsSummaryFixture.debugElement;
    deviceDetailsSummary = deviceDetailsSummaryFixture.componentInstance;
    deviceDetailsSummary.id = serial;
    deviceDetailsSummaryFixture.detectChanges();
  });

  afterEach(() => {
    deviceDetailsSummaryFixture.destroy();
  });

  it('should gets initialized correctly', () => {
    const textContent = getTextContent(el);
    expect(textContent).toContain('Battery');
    expect(deviceDetailsSummary).toBeTruthy();
  });

  it('should calls the tfc client api method getDeviceInfo correctly',
     async () => {
       await deviceDetailsSummaryFixture.whenStable();
       expect(tfcClient.getDeviceInfo).toHaveBeenCalledTimes(1);
     });

  it('should only calls the tfc client api method getDeviceInfo once',
     async () => {
       await deviceDetailsSummaryFixture.whenStable();
       expect(tfcClient.getDeviceInfo).not.toBeGreaterThan(1);
     });

  it('should NOT render device serial.', () => {
    deviceDetailsSummary.data = mockDeviceInfo;
    deviceDetailsSummaryFixture.detectChanges();
    const compiled = deviceDetailsSummaryFixture.debugElement.nativeElement;
    expect(compiled.querySelector('.table-content').textContent)
        .not.toContain(serial);
  });

  it('can show error when getDeviceInfo returns 404', () => {
    tfcClient.getDeviceInfo.calls.reset();
    tfcClient.getDeviceInfo.and.returnValue(throwError({'status': 404}));
    deviceDetailsSummary.loadDevice(serial);
    expect(notifierSpy.showError).toHaveBeenCalled();
  });

  it('should remove device correctly', () => {
    deviceDetailsSummary.removeDevice();
    expect(tfcClient.removeDevice).toHaveBeenCalledWith(serial, hostname);
    expect(tfcClient.removeDevice).toHaveBeenCalledTimes(1);
  });

  it('calls getLogUrl and returns correctly', () => {
    const url = `http://server01/hostname:${HOSTNAME}%20s%2F${DEVICE_SERIAL}`;
    deviceDetailsSummary.logUrl = url;
    const device = 'device01';
    const deviceInfo = newMockLabDeviceInfo(device);
    const logUrl = deviceDetailsSummary.getLogUrl(deviceInfo);
    expect(logUrl).toEqual(
        url.replace(HOSTNAME, deviceInfo.hostname || '')
            .replace(DEVICE_SERIAL, deviceInfo.device_serial));
  });
});
