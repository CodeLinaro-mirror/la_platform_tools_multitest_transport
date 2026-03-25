/**
 * Copyright 2026 Google LLC
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
import {COMMA, ENTER} from '@angular/cdk/keycodes';
import {
  ChangeDetectionStrategy,
  ChangeDetectorRef,
  Component,
  OnDestroy,
  OnInit,
  inject,
} from '@angular/core';
import {MatChipInputEvent} from '@angular/material/chips';
import {ReplaySubject} from 'rxjs';
import {finalize, first, takeUntil} from 'rxjs/operators';

import {MttClient} from '../services/mtt_client';
import {PrivateNodeConfig} from '../services/mtt_models';
import {Notifier} from '../services/notifier';
import {FormChangeTracker} from '../shared/can_deactivate';
import {buildApiErrorMessage} from '../shared/util';

/** A component for displaying notifications setting form */
@Component({
  standalone: false,
  selector: 'notifications-form',
  styleUrls: ['notifications_form.css'],
  templateUrl: './notifications_form.ng.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class NotificationsForm
  extends FormChangeTracker
  implements OnInit, OnDestroy
{
  isLoading = false;
  readonly separatorKeysCodes = [ENTER, COMMA] as const;

  private readonly notifier = inject(Notifier);
  private readonly mtt = inject(MttClient);
  private readonly liveAnnouncer = inject(LiveAnnouncer);
  private readonly cdr = inject(ChangeDetectorRef);

  constructor() {
    super();
  }

  privateNodeConfig!: Partial<PrivateNodeConfig>;
  private readonly destroy = new ReplaySubject<void>();

  // Use a getter/setter to bind the checkbox for TEST_RUN_ATTEMPT_COMPLETED
  get notifyTestRunAttemptCompleted(): boolean {
    if (!this.privateNodeConfig?.notification_config?.events) return false;
    return this.privateNodeConfig.notification_config.events.includes(
      'TEST_RUN_ATTEMPT_COMPLETED',
    );
  }

  set notifyTestRunAttemptCompleted(value: boolean) {
    if (!this.privateNodeConfig.notification_config) {
      this.privateNodeConfig.notification_config = {};
    }
    if (!this.privateNodeConfig.notification_config.events) {
      this.privateNodeConfig.notification_config.events = [];
    }
    const idx = this.privateNodeConfig.notification_config.events.indexOf(
      'TEST_RUN_ATTEMPT_COMPLETED',
    );
    if (value && idx === -1) {
      this.privateNodeConfig.notification_config.events.push('TEST_RUN_ATTEMPT_COMPLETED');
    } else if (!value && idx !== -1) {
      this.privateNodeConfig.notification_config.events.splice(idx, 1);
    }
  }

  ngOnInit() {
    this.load();
  }

  ngOnDestroy() {
    this.destroy.next();
    this.liveAnnouncer.clear();
  }

  load() {
    this.isLoading = true;
    this.liveAnnouncer.announce('Loading', 'polite');

    this.mtt
      .getPrivateNodeConfig()
      .pipe(
        takeUntil(this.destroy),
        finalize(() => {
          this.isLoading = false;
          this.cdr.detectChanges();
        }),
      )
      .subscribe(
        (nodeConfigRes) => {
          this.privateNodeConfig = nodeConfigRes;
          if (!this.privateNodeConfig.notification_config) {
            this.privateNodeConfig.notification_config = {};
          }
          if (!this.privateNodeConfig.notification_config.receiver_addresses) {
            this.privateNodeConfig.notification_config.receiver_addresses = [];
          }
          if (!this.privateNodeConfig.notification_config.events) {
            this.privateNodeConfig.notification_config.events = [];
          }
          this.liveAnnouncer.announce(
            'Notifications settings loaded',
            'assertive',
          );
          this.cdr.detectChanges();
        },
        (error) => {
          this.notifier.showError(
            'Failed to load notifications settings.',
            buildApiErrorMessage(error),
          );
        },
      );
  }

  addReceiver(event: MatChipInputEvent): void {
    const value = (event.value || '').trim();

    if (value) {
      this.privateNodeConfig.notification_config!.receiver_addresses!.push(value);
    }

    // Clear the input value
    event.chipInput!.clear();
  }

  removeReceiver(receiver: string): void {
    const index =
      this.privateNodeConfig.notification_config!.receiver_addresses!.indexOf(receiver);

    if (index >= 0) {
      this.privateNodeConfig.notification_config!.receiver_addresses!.splice(index, 1);
      this.liveAnnouncer.announce(`Removed ${receiver}`);
    }
  }

  onSubmit() {
    const resultNodeConfig: PrivateNodeConfig = {...this.privateNodeConfig} as PrivateNodeConfig;

    this.mtt
      .updatePrivateNodeConfig(resultNodeConfig)
      .pipe(first())
      .subscribe(
        (result) => {
          super.resetForm();
          this.notifier.showMessage('Notifications settings updated');
          this.cdr.detectChanges();
        },
        (error) => {
          this.notifier.showError(
            'Failed to update notifications settings.',
            buildApiErrorMessage(error),
          );
        },
      );
  }
}
