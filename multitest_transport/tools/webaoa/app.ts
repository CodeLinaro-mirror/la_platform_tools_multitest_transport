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

import {Component} from '@angular/core';

import {AoaDevice} from './device/device';

// True if Google Analytics is enabled (defined in index.html).
declare var analyticsEnabled: boolean;

/** Main application {@link Component}. */
@Component({
  standalone: false,
  selector: 'aoa-app',
  templateUrl: './app.ng.html',
  styleUrls: ['./app.css'],
})
export class AppComponent {
  /** True if Google Analytics is enabled. */
  readonly analyticsEnabled =
      typeof analyticsEnabled !== 'undefined' && analyticsEnabled;
  /** True if current context is secure. */
  readonly isSecureContext = isSecureContext;
  /** True if current context is secure and the browser supports WebUSB. */
  readonly isWebUsbSupported = !!navigator.usb;
  /** Device selected for use in the workflow editor. */
  device?: AoaDevice;
  /** True if the workflow editor is visible. */
  editing = false;

  /** Switch to workflow editor without selecting a device. */
  editWithoutDevice() {
    this.device = undefined;
    this.editing = true;
  }

  /** Select a device and switch to workflow editor. */
  selectDevice(device: AoaDevice) {
    this.device = device;
    this.editing = true;
  }

  /** Unselect device if necessary and return to device selection. */
  returnToDeviceSelection() {
    this.device = undefined;
    this.editing = false;
  }
}
