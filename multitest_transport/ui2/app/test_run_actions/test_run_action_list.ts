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
import {Component, OnDestroy, OnInit, ChangeDetectionStrategy} from '@angular/core';
import {ReplaySubject} from 'rxjs';
import {delay, finalize, takeUntil} from 'rxjs/operators';

import {MttClient} from '../services/mtt_client';
import {AuthorizationState, TestRunAction} from '../services/mtt_models';
import {Notifier} from '../services/notifier';
import {buildApiErrorMessage} from '../shared/util';

/** Displays a list of test run actions. */
@Component({
  changeDetection: ChangeDetectionStrategy.Eager,standalone: false,
  selector: 'test-run-action-list',
  styleUrls: ['test_run_action_list.css'],
  templateUrl: './test_run_action_list.ng.html',
})
export class TestRunActionList implements OnInit, OnDestroy {
  readonly AuthorizationState = AuthorizationState;
  isLoading = false;
  actions: TestRunAction[] = [];

  private readonly destroy = new ReplaySubject<void>();

  constructor(
      private readonly liveAnnouncer: LiveAnnouncer,
      private readonly notifier: Notifier, private readonly mtt: MttClient) {}

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

    // Add short delay to allow device action changes to propagate.
    this.mtt.testRunActions.list()
        .pipe(takeUntil(this.destroy))
        .pipe(finalize(() => {
          this.isLoading = false;
        }))
        .subscribe(
            actions => {
              this.actions = actions;
              this.liveAnnouncer.announce(
                  'Test run actions loaded', 'assertive');
            },
            error => {
              this.notifier.showError(
                  'Failed to load test run actions.',
                  buildApiErrorMessage(error));
            },
        );
  }

  /** Authorize a test run action and reload. */
  authorize(action: TestRunAction) {
    this.mtt.testRunActions.authorize(action.id)
        .pipe(delay(500))  // Delay for data to be persisted
        .subscribe(
            () => {
              this.load();
            },
            error => {
              this.notifier.showError(
                  'Failed to authorize test run action.',
                  buildApiErrorMessage(error));
            });
  }

  /** Authorize a test run action with a service account JSON key and reload. */
  uploadKeyfile(action: TestRunAction, keyFile?: File) {
    if (!keyFile) {
      return;
    }
    this.mtt.testRunActions.authorizeWithServiceAccount(action.id, keyFile)
        .pipe(delay(500))  // Delay for data to be persisted
        .subscribe(
            () => {
              this.load();
            },
            error => {
              this.notifier.showError(
                  'Failed to authorize test run action.',
                  buildApiErrorMessage(error));
            });
  }

  /** Revoke a test run action's authorization and reload. */
  revokeAuthorization(action: TestRunAction) {
    this.mtt.testRunActions.unauthorize(action.id)
        .pipe(delay(500))  // Delay for data to be persisted
        .subscribe(
            () => {
              this.load();
            },
            error => {
              this.notifier.showError(
                  'Failed to revoke test run action authorization.',
                  buildApiErrorMessage(error));
            });
  }

  /** Delete a test run action after confirmation. */
  delete(action: TestRunAction) {
    this.notifier
        .confirm(
            `Do you really want to delete test run action '${action.name}'?`,
            'Delete test run action')
        .subscribe(confirmed => {
          if (!confirmed) {
            return;
          }
          this.mtt.testRunActions.delete(action.id).subscribe(
              () => {
                const index = this.actions.findIndex(a => a.id === action.id);
                if (index !== -1) {
                  this.actions.splice(index, 1);
                }
                this.notifier.showMessage(
                    `Test run action '${action.name}' deleted`);
              },
              error => {
                this.notifier.showError(
                    `Failed to delete test run action.`,
                    buildApiErrorMessage(error));
              });
        });
  }
}
