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

import {Component, Input} from '@angular/core';

import {DeviceInfo} from '../services/tfc_models';

/** A component for displaying a given list of devices. */
@Component({
  standalone: false,
  selector: 'simple-device-list',
  styleUrls: ['simple_device_list.css'],
  templateUrl: './simple_device_list.ng.html',
})
export class SimpleDeviceList {
  @Input()
  displayedDeviceInfoColumns: string[] = [
    'device_serial', 'hostname', 'product', 'product_variant', 'build_id',
    'battery_level', 'sim_status', 'state'
  ];
  @Input() deviceInfos: DeviceInfo[] = [];

  /**
   * When people with disability clicked on the checkbox, they don't
   * no what they are checking. This method with genereate the aria-label
   * for checkbox in the table.
   */
  getDeviceAriaMessage(row: DeviceInfo): string {
    return `Device with serial ${row.device_serial}`;
  }
}
