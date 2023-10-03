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
import {Component, Inject, Input, OnChanges, OnDestroy, OnInit, SimpleChanges} from '@angular/core';
import {MAT_DIALOG_DATA} from '@angular/material/dialog';
import {MatTabChangeEvent} from '@angular/material/tabs';
import {Router} from '@angular/router';
import {ReplaySubject} from 'rxjs';
import {takeUntil} from 'rxjs/operators';

import {FeedbackService} from '../services/feedback_service';
import {LabDeviceInfo, NoteType, SurveyTrigger} from '../services/mtt_lab_models';
import {Notifier} from '../services/notifier';
import {DeviceSerialWithDisplay, StorageService} from '../services/storage_service';
import {TfcClient} from '../services/tfc_client';
import {buildApiErrorMessage} from '../shared/util';

/**
 * Data format when passed to DeviceDetails.
 */
export interface DeviceDetailsDialogParams {
  id: string;
  newWindow: boolean;
}

/**
 * A component for displaying device details information.
 */
@Component({
  selector: 'device-details',
  styleUrls: ['device_details.css'],
  templateUrl: './device_details.ng.html',
})
export class DeviceDetails implements OnChanges, OnDestroy, OnInit {
  @Input() id = '';
  @Input() newWindow = false;
  readonly noteType = NoteType.DEVICE;
  previousRoute = '';
  previousId = '';
  readonly defaultBackRoute = 'devices';
  isLoading = false;
  private readonly destroy = new ReplaySubject<void>();
  isModalMode = false;
  deviceSerialsWithDisplay: DeviceSerialWithDisplay[] = [];
  data?: LabDeviceInfo;

  constructor(
      private readonly feedbackService: FeedbackService,
      private readonly liveAnnouncer: LiveAnnouncer,
      private readonly notifier: Notifier,
      private readonly router: Router,
      private readonly storageService: StorageService,
      private readonly tfcClient: TfcClient,
      @Inject(MAT_DIALOG_DATA) readonly params?:
          DeviceDetailsDialogParams,
  ) {}

  ngOnChanges(changes: SimpleChanges) {
    if (changes['id'] && !changes['id'].firstChange) {
      this.load(changes['id'].currentValue);
      this.appendDefaultOption();
    }
  }

  ngOnInit() {
    if (this.params && this.params.id) {
      this.isModalMode = true;
      this.id = this.params.id;
      this.newWindow = this.params.newWindow;
    }
    this.deviceSerialsWithDisplay = this.storageService.deviceList;
    this.load(this.id);
    this.appendDefaultOption();
  }

  ngOnDestroy() {
    this.destroy.next();
  }

  get deviceSerials() {
    return this.deviceSerialsWithDisplay.map(
        deviceSerialWithDisplay => deviceSerialWithDisplay.serial);
  }

  load(deviceSerial: string, switchParam = false) {
    this.isLoading = true;
    if (switchParam) {
      this.updateUrlByDeviceSerial(deviceSerial);
    }
    this.liveAnnouncer.announce('Loading', 'polite');
    this.tfcClient.getDeviceInfo(deviceSerial)
        .pipe(
            takeUntil(this.destroy),
            )
        .subscribe(
            (result) => {
              this.data = result;
              this.liveAnnouncer.announce('Device info loaded', 'assertive');
            },
            (error) => {
              this.notifier.showError(
                  `Failed to get device with id ${deviceSerial}.`,
                  buildApiErrorMessage(error));
            },
        );
  }

  closeLoading() {
    // To prevent ExpressionChangedAfterItHasBeenCheckedError: Expression has
    // changed after it was checked.
    setTimeout(() => {
      this.isLoading = false;
    }, 0);
  }

  back() {
    window.history.back();
  }

  appendDefaultOption() {
    if (this.id && !this.deviceSerials.includes(this.id)) {
      this.deviceSerialsWithDisplay.push({
        serial: this.id,
        serialForDisplay: this.id,
      });
    }
  }

  startDeviceHistoryHats(event: MatTabChangeEvent) {
    if (event.tab.textLabel === 'History') {
      this.feedbackService.startSurvey(SurveyTrigger.DEVICE_HISTORY);
    }
  }

  startDeviceNavigationHats() {
    this.feedbackService.startSurvey(SurveyTrigger.DEVICE_NAVIGATION);
  }

  /** Updates current URL string. */
  updateUrlByDeviceSerial(deviceSerial: string) {
    const url = this.router.serializeUrl(
        this.router.createUrlTree(['/devices', deviceSerial]));
    this.router.navigate([url], {replaceUrl: true});
  }
}
