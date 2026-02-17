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

import {Component, OnInit, ChangeDetectionStrategy} from '@angular/core';
import {first} from 'rxjs/operators';

import {MttClient} from '../services/mtt_client';
import {CredentialsInfo} from '../services/mtt_models';
import {Notifier} from '../services/notifier';
import {buildApiErrorMessage, delay, reloadPage} from '../shared/util';

/** A component for displaying the login button. */
@Component({
  changeDetection: ChangeDetectionStrategy.Eager,standalone: false,
  selector: 'login-button',
  styleUrls: ['login_button.css'],
  templateUrl: './login_button.ng.html',
})
export class LoginButton implements OnInit {
  constructor(
      private readonly mtt: MttClient, private readonly notifier: Notifier) {}

  defaultCredentials?: CredentialsInfo;

  ngOnInit() {
    this.load();
  }

  load() {
    this.mtt.getPrivateNodeConfig().pipe(first()).subscribe(
        (res) => {
          this.defaultCredentials = res.default_credentials;
        },
        error => {
          this.notifier.showError(
              'Failed to load private node config.',
              buildApiErrorMessage(error));
        },
    );
  }

  /** Authorize the default service account JSON key. */
  setDefaultServiceAccount(keyFile?: File) {
    if (!keyFile) {
      return;
    }
    this.mtt.setDefaultServiceAccount(keyFile)
        .pipe(delay(500))  // Delay for data to be persisted
        .subscribe(
            () => {
              this.notifier.showMessage(`Default service account set`);
              reloadPage(100);  // Reload all components on the page
            },
            error => {
              this.notifier.showError(
                  `Failed to set default service account.`,
                  buildApiErrorMessage(error));
            });
  }

  removeDefaultServiceAccount() {
    this.mtt.removeDefaultServiceAccount()
        .pipe(delay(500))  // Delay for data to be persisted
        .subscribe(
            () => {
              this.notifier.showMessage(`Default service account removed`);
              reloadPage(100);  // Reload all components on the page
            },
            error => {
              this.notifier.showError(
                  `Failed to remove default service account.`,
                  buildApiErrorMessage(error));
            });
  }
}
