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
import {Component, EventEmitter, Inject, Input, OnDestroy, Output, ChangeDetectionStrategy} from '@angular/core';
import {ReplaySubject} from 'rxjs';
import {takeUntil} from 'rxjs/operators';

import {APP_DATA, AppData} from '../services';
import {HostAssignInfo, LabHostInfo} from '../services/mtt_lab_models';
import {Notifier} from '../services/notifier';
import {TfcClient} from '../services/tfc_client';
import {HostRecoveryStateRequest, RecoveryState} from '../services/tfc_models';

/** A button for users to mark hosts recovery state as 'VERIFIED'. */
@Component({
  changeDetection: ChangeDetectionStrategy.Eager,standalone: false,
  selector: 'mark-host-as-fixed-button',
  styleUrls: ['mark_host_as_fixed_button.css'],
  templateUrl: './mark_host_as_fixed_button.ng.html',
})
export class MarkHostAsFixedButton implements OnDestroy {
  @Input() disabled: boolean = false;
  @Input() host?: LabHostInfo;
  @Output() readonly hostMarkedAsFixed = new EventEmitter<string>();
  @Output() readonly hostAssigneeChange = new EventEmitter<HostAssignInfo>();

  private readonly destroy = new ReplaySubject<void>();
  readonly RecoveryState = RecoveryState;

  constructor(
      private readonly tfcClient: TfcClient,
      private readonly notifier: Notifier,
      private readonly liveAnnouncer: LiveAnnouncer,
      @Inject(APP_DATA) private readonly appData: AppData,
  ) {}

  toggleHostFixedState(event: MouseEvent) {
    event.stopPropagation();
    if (!this.host) {
      return;
    }
    if (!this.appData.userNickname) {
      this.notifier.showError('Please sign in');
      return;
    }

    const currentState = this.host.recoveryState;
    const fixedMsg = `The host's recovery state has been marked as FIXED`;
    const undoMsg =
        `The host's recovery state has been marked back as ASSIGNED`;
    const errMsg = `Failed to mark the host's recovery state as FIXED`;
    const msg = currentState === RecoveryState.FIXED ? undoMsg : fixedMsg;

    const nextState = currentState === RecoveryState.FIXED ?
        RecoveryState.ASSIGNED :
        RecoveryState.FIXED;

    const hostRecoveryStateRequests = [{
      hostname: this.host.hostname,
      recovery_state: nextState,
      assignee: this.appData.userNickname
    } as HostRecoveryStateRequest];

    this.tfcClient.batchSetHostsRecoveryStates(hostRecoveryStateRequests)
        .pipe(takeUntil(this.destroy))
        .subscribe(
            () => {
              this.updateRecoveryStateAndAssignee(nextState);
              this.hostMarkedAsFixed.emit(this.host?.hostname);
              this.notifier.showMessage(msg);
              this.liveAnnouncer.announce(msg, 'assertive');
            },
            () => {
              this.notifier.showError(errMsg);
            });
  }

  updateRecoveryStateAndAssignee(nextState: RecoveryState) {
    if (!this.host) {
      return;
    }
    this.host.recoveryState = nextState;

    // A host can be mark as fixed before has an assignee. In this
    // case, when the host is marked as fixed, the host should be also
    // assigned to current user.
    if (this.appData.userNickname &&
        this.host.assignee !== this.appData.userNickname) {
      this.host.assignee = this.appData.userNickname;
      const assignInfo: HostAssignInfo = {
        hostnames: [this.host.hostname],
        assignee: this.appData.userNickname
      };
      this.hostAssigneeChange.emit(assignInfo);
    }
  }

  ngOnDestroy() {
    this.destroy.next();
  }
}
