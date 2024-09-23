/**
 * @license
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

import {Component, EventEmitter, OnDestroy, Output} from '@angular/core';
import {ReplaySubject} from 'rxjs';
import {takeUntil} from 'rxjs/operators';

import {AoaDevice} from './device';
import {DeviceManager} from './device_manager';

/** Displays a list of connected AOA-compatible devices to select from. */
@Component({
  standalone: false,
  selector: 'device-list',
  templateUrl: './device_list.ng.html',
  styleUrls: ['./device_list.css'],
})
export class DeviceList implements OnDestroy {
  private readonly destroy = new ReplaySubject<void>();
  /** List of connected AOA-compatible devices. */
  devices: AoaDevice[] = [];
  /** Emits when a device is selected. */
  @Output() readonly selectionChange = new EventEmitter<AoaDevice>();

  constructor(private readonly deviceManager: DeviceManager) {
    this.loadDevices();
    this.deviceManager.onConnectionChange()
        .pipe(takeUntil(this.destroy))
        .subscribe(() => {
          this.loadDevices();
        });
  }

  ngOnDestroy(): void {
    this.destroy.next();
  }

  /** Reloads the device list. */
  private loadDevices() {
    this.deviceManager.getDevices().then(devices => this.devices = devices);
  }

  /** Prompts user to pair a new device. */
  requestDevice() {
    this.deviceManager.requestDevice();
  }
}
