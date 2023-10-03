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

import {Injectable, OnDestroy} from '@angular/core';
import {ReplaySubject} from 'rxjs';

/** Key for storing host list in local storage. */
export const HOST_LIST_KEY = 'atsHostList';

/** Key for storing device list in local storage. */
export const DEVICE_LIST_KEY = 'atsDeviceList';

/** Interface for device serial with serial for display. */
export interface DeviceSerialWithDisplay {
  serial: string;
  serialForDisplay: string;
}

/**
 * Service to store list of hostname and device serial number for dropdown
 * list in host and device details page.
 */
@Injectable({
  providedIn: 'root',
})
export class StorageService implements OnDestroy {
  private readonly destroyed = new ReplaySubject<void>(1);

  private wrappedHostList: string[] = [];
  private wrappedDeviceList: DeviceSerialWithDisplay[] = [];

  ngOnDestroy() {
    this.destroyed.next();
    this.destroyed.complete();
  }

  set hostList(hostList: string[]) {
    this.wrappedHostList = hostList;
  }

  get hostList() {
    if (!this.wrappedHostList.length) {
      this.wrappedHostList = this.getListFromLocalStorage(HOST_LIST_KEY);
    }
    return this.wrappedHostList;
  }

  set deviceList(deviceList: DeviceSerialWithDisplay[]) {
    this.wrappedDeviceList = deviceList;
  }

  get deviceList() {
    if (!this.wrappedDeviceList.length) {
      this.wrappedDeviceList = this.getListFromLocalStorage(DEVICE_LIST_KEY);
    }
    return this.wrappedDeviceList;
  }

  getListFromLocalStorage<T>(key: string): T[] {
    let idList: T[] = [];
    const ids = window.localStorage.getItem(key);
    if (ids) {
      idList = JSON.parse(ids) as T[];
      window.localStorage.removeItem(key);
    }
    return idList;
  }

  saveHostListInLocalStorage(hostList: string[]) {
    this.updateLocalStorage(HOST_LIST_KEY, hostList);
  }

  saveDeviceListInLocalStorage(deviceList: DeviceSerialWithDisplay[]) {
    this.updateLocalStorage(DEVICE_LIST_KEY, deviceList);
  }

  private updateLocalStorage<T>(key: string, list: T[]) {
    window.localStorage.setItem(key, JSON.stringify(list));
  }
}
