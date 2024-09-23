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
import {Component, EventEmitter, Inject, Input, OnChanges, OnDestroy, OnInit, Output, SimpleChanges} from '@angular/core';
import {Notifier} from 'google3/third_party/py/multitest_transport/ui2/app/services/notifier';
import {assertRequiredInput} from 'google3/third_party/py/multitest_transport/ui2/app/shared/util';
import {of as observableOf, ReplaySubject, throwError} from 'rxjs';
import {catchError, filter, finalize, switchMap, takeUntil} from 'rxjs/operators';

import {APP_DATA, AppData} from '../services';
import {DEVICE_SERIAL, HOSTNAME, LabDeviceInfo, REMOVE_DEVICE_MESSAGE} from '../services/mtt_lab_models';
import {TfcClient} from '../services/tfc_client';
import {TestHarness} from '../services/tfc_models';
import {UserService} from '../services/user_service';
import {buildApiErrorMessage} from '../shared/util';

/** Readonly form for device summary. */
@Component({
  standalone: false,
  selector: 'device-details-summary',
  styleUrls: ['./device_details_summary.css'],
  templateUrl: './device_details_summary.ng.html',
})
export class DeviceDetailsSummary implements OnChanges, OnInit, OnDestroy {
  @Input() id!: string;
  @Output() readonly dataLoadedEvent = new EventEmitter<boolean>();
  @Input() newWindow = false;

  private readonly destroy = new ReplaySubject<void>();

  data?: LabDeviceInfo;
  showLogLink = false;
  logUrl = '';

  readonly testHarness = TestHarness;

  constructor(
      private readonly liveAnnouncer: LiveAnnouncer,
      private readonly notifier: Notifier,
      private readonly tfcClient: TfcClient,
      readonly userService: UserService,
      @Inject(APP_DATA) private readonly appData: AppData,
  ) {
    if (this.appData.isGoogle) {
      this.showLogLink = true;
      this.logUrl = appData.logUrl || '';
    }
  }

  ngOnChanges(changes: SimpleChanges) {
    if (changes['id'] && !changes['id'].firstChange) this.loadDevice(this.id);
  }

  ngOnInit() {
    assertRequiredInput(this.id, 'id', 'device-detail-summary');
    this.loadDevice(this.id);
  }

  ngOnDestroy() {
    this.destroy.next();
  }

  loadDevice(id: string) {
    this.liveAnnouncer.announce('Loading', 'polite');
    this.tfcClient.getDeviceInfo(id)
        .pipe(
            takeUntil(this.destroy),
            finalize(() => {
              this.dataLoadedEvent.emit(true);
            }),
            )
        .subscribe(
            (result) => {
              this.data = result;
              this.logUrl = this.getLogUrl(result);
              this.liveAnnouncer.announce('Device info loaded', 'assertive');
            },
            (error) => {
              this.notifier.showError(
                  `Failed to get device with id ${id}.`,
                  buildApiErrorMessage(error));
            },
        );
  }

  /** When device state is GONE, user can remove(hide) the device. */
  removeDevice() {
    this.notifier.confirm('', REMOVE_DEVICE_MESSAGE, 'Remove device', 'Cancel')
        .pipe(
            switchMap((result) => {
              if (!result || !this.data) return observableOf(false);
              return this.tfcClient
                  .removeDevice(this.id, this.data.hostname || '')
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
              this.notifier.showMessage('Device removed');
            },
            () => {
              this.notifier.showError(`Failed to remove device ${this.id}`);
            });
  }

  getLogUrl(device: LabDeviceInfo): string {
    return this.logUrl.replace(HOSTNAME, device.hostname || '')
        .replace(DEVICE_SERIAL, device.device_serial);
  }
}
