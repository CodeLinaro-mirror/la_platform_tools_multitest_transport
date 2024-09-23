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
import {Component} from '@angular/core';
import {Router} from '@angular/router';
import {ReplaySubject} from 'rxjs';
import {finalize, takeUntil} from 'rxjs/operators';

import {FeedbackService} from '../services/feedback_service';
import {SurveyTrigger} from '../services/mtt_lab_models';
import {Notifier} from '../services/notifier';
import {TfcClient} from '../services/tfc_client';

/** Search a host or a device then navigate to its page. */
@Component({
  standalone: false,
  selector: 'host-device-search',
  styleUrls: ['host_device_search.css'],
  templateUrl: './host_device_search.ng.html',
})
export class HostDeviceSearch {
  private readonly destroy = new ReplaySubject<void>();

  constructor(
      private readonly feedbackService: FeedbackService,
      private readonly liveAnnouncer: LiveAnnouncer,
      private readonly notifier: Notifier, private readonly router: Router,
      private readonly tfcClient: TfcClient) {}

  /** Query from device/host api then redirect to the page. */
  onEnter(name: string) {
    this.liveAnnouncer.announce('Searching', 'polite');
    // Step 1: Search on the devices.
    this.tfcClient.getDeviceInfo(name)
        .pipe(
            takeUntil(this.destroy),
            finalize(() => {
              this.liveAnnouncer.announce(`${name} loaded', 'assertive`);
            }),
            )
        .subscribe(
            deviceInfo => {
              if (deviceInfo && deviceInfo.device_serial) {
                this.router.navigateByUrl(`/devices/${name}`);
              } else {
                this.notifier.showError(`Incorrect device data '${name}'`);
              }
            },
            error => {
              // Step 2: Search on the hosts.
              if (error.status === 404) {
                this.checkHostnameAndRedirect(name);
              } else {
                this.notifier.showError(`Failed to load device '${name}'`);
              }
            },
        );
    this.feedbackService.startSurvey(SurveyTrigger.SEARCH_BOX);
  }

  /** Try to find the name on the hosts and redirect to host detail page. */
  checkHostnameAndRedirect(name: string) {
    this.tfcClient.getHostInfo(name)
        .pipe(takeUntil(this.destroy))
        .subscribe(
            hostInfo => {
              if (hostInfo && hostInfo.hostname) {
                this.router.navigateByUrl(`/hosts/${name}`);
              } else {
                // Can't find the name on the hosts.
                this.notifier.showError(`Incorrect host data '${name}'`);
              }
            },
            error => {
              // Both devices and hosts don't have the name.
              if (error.status === 404) {
                this.notifier.showWarning(`'${name}' not found`);
              } else {
                this.notifier.showError(`Failed to load host ${name}`);
              }
            },
        );
  }
}
