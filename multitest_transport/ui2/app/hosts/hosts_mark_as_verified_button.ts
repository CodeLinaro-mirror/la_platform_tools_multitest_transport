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
import {Component, EventEmitter, Input, OnDestroy, Output, ChangeDetectionStrategy} from '@angular/core';
import {ReplaySubject} from 'rxjs';
import {takeUntil} from 'rxjs/operators';

import {Notifier} from '../services/notifier';
import {TfcClient} from '../services/tfc_client';
import {HostRecoveryStateRequest, RecoveryState} from '../services/tfc_models';

/** A button for users to mark hosts recovery state as 'VERIFIED'. */
@Component({
  changeDetection: ChangeDetectionStrategy.Eager,standalone: false,
  selector: 'hosts-mark-as-verified-button',
  styleUrls: ['hosts_mark_as_verified_button.css'],
  templateUrl: './hosts_mark_as_verified_button.ng.html',
})
export class HostsMarkAsVerifiedButton implements OnDestroy {
  @Input() hostNames: string[] = [];
  @Input() disabled: boolean = false;
  @Output() readonly hostsMarkedAsVerified = new EventEmitter<string[]>();

  protected readonly destroy = new ReplaySubject<void>();

  constructor(
      protected readonly tfcClient: TfcClient,
      protected readonly notifier: Notifier,
      protected readonly liveAnnouncer: LiveAnnouncer,
  ) {}

  markHostsAsVerified() {
    if (this.hostNames.length > 0) {
      const hostRecoveryStateRequests = this.hostNames.map(hostname => {
        return {
          hostname,
          recovery_state: RecoveryState.VERIFIED,
        } as HostRecoveryStateRequest;
      });
      this.tfcClient.batchSetHostsRecoveryStates(hostRecoveryStateRequests)
          .pipe(takeUntil(this.destroy))
          .subscribe(
              () => {
                this.hostsMarkedAsVerified.emit(this.hostNames);
                this.notifier.showMessage('Hosts marked as verified');
                this.liveAnnouncer.announce(
                    'Hosts marked as verified', 'assertive');
              },
              () => {
                this.notifier.showError('Failed to mark hosts as verified');
              });
    }
  }

  ngOnDestroy() {
    this.destroy.next();
  }
}
