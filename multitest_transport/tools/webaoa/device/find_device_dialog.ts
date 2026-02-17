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

import {Component, Inject, ChangeDetectionStrategy} from '@angular/core';
import {MAT_DIALOG_DATA, MatDialogRef} from '@angular/material/dialog';

import {DeviceManager} from './device_manager';

/**
 * Dialog shown when a device connection is unexpectedly lost, prompting the
 * user to reconnect the device.
 */
@Component({
  changeDetection: ChangeDetectionStrategy.Eager,standalone: false,
  template: `
    <h1 matDialogTitle>Device connection lost</h1>
    <div matDialogContent>
      Device was unpaired or disconnected. This can occur the first time you
      use a device as <i>WebAOA</i> requires access to your device in
      <i>accessory mode</i>.<br>
      Click <b>Find Device</b> and reselect it.
    </div>
    <div matDialogActions align="end">
      <button mat-button mat-dialog-close>Cancel</button>
      <button mat-raised-button color="accent" (click)="findDevice()">
        Find Device
      </button>
    </div>
  `,
})
export class FindDeviceDialog {
  constructor(
      private readonly dialogRef: MatDialogRef<FindDeviceDialog>,
      @Inject(MAT_DIALOG_DATA) private readonly serialNumber: string,
      private readonly deviceManager: DeviceManager) {}

  /** Prompt the user to find the device using its serial number. */
  findDevice() {
    this.deviceManager.requestDevice(this.serialNumber).then(device => {
      this.dialogRef.close(device);
    });
  }
}
