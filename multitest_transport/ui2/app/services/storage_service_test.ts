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

import {DEVICE_LIST_KEY, DeviceSerialWithDisplay, HOST_LIST_KEY, StorageService} from './storage_service';

describe('StorageService', () => {
  let service: StorageService;

  beforeEach(() => {
    service = new StorageService();
  });

  it('should get host list from local storage if host list in service is empty',
     () => {
       spyOn(service, 'getListFromLocalStorage').and.callThrough();
       const hostnames = ['host3', 'host4'];
       window.localStorage.setItem(HOST_LIST_KEY, JSON.stringify(hostnames));
       const hostList = service.hostList;
       expect(service.getListFromLocalStorage).toHaveBeenCalledTimes(1);
       expect(service.getListFromLocalStorage)
           .toHaveBeenCalledWith(HOST_LIST_KEY);
       expect(hostList).toEqual(hostnames);
     });

  it('should get device list from local storage if device list in service is empty',
     () => {
       spyOn(service, 'getListFromLocalStorage').and.callThrough();
       const deviceSerials: DeviceSerialWithDisplay[] = [
         {serial: 'device1', serialForDisplay: 'display1'},
         {serial: 'device2', serialForDisplay: 'display2'},
       ];
       window.localStorage.setItem(
           DEVICE_LIST_KEY, JSON.stringify(deviceSerials));
       const deviceList = service.deviceList;
       expect(service.getListFromLocalStorage).toHaveBeenCalledTimes(1);
       expect(service.getListFromLocalStorage)
           .toHaveBeenCalledWith(DEVICE_LIST_KEY);
       expect(deviceList).toEqual(deviceSerials);
     });

  it('should set host list into local storage correctly', () => {
    spyOn(window.localStorage, 'setItem');
    const hostList = ['host4', 'host5'];
    service.saveHostListInLocalStorage(hostList);
    expect(window.localStorage.setItem)
        .toHaveBeenCalledWith(HOST_LIST_KEY, JSON.stringify(hostList));
  });

  it('should set device list into local storage correctly', () => {
    spyOn(window.localStorage, 'setItem');
    const deviceList: DeviceSerialWithDisplay[] = [
      {serial: 'device4', serialForDisplay: 'display4'},
      {serial: 'device5', serialForDisplay: 'display5'},
    ];
    service.saveDeviceListInLocalStorage(deviceList);
    expect(window.localStorage.setItem)
        .toHaveBeenCalledWith(DEVICE_LIST_KEY, JSON.stringify(deviceList));
  });
});
