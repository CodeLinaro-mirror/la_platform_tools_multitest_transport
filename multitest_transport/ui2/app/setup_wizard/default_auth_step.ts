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

import {Component, OnInit} from '@angular/core';
import {first} from 'rxjs/operators';

import {MttClient} from '../services/mtt_client';
import {CredentialsInfo} from '../services/mtt_models';
import {Notifier} from '../services/notifier';
import {buildApiErrorMessage, delay} from '../shared/util';

/** A component for restore a backup config exported from an MTT instance. */
@Component({
  standalone: false,
  selector: 'default-auth-step',
  styleUrls: ['default_auth_step.css'],
  templateUrl: './default_auth_step.ng.html',
})
export class DefaultAuthStep implements OnInit {
  isLoading = false;
  defaultCredentials?: CredentialsInfo;

  constructor(
      private readonly mttClient: MttClient,
      private readonly notifier: Notifier) {}

  ngOnInit() {
    this.load();
  }

  load() {
    this.isLoading = true;
    this.mttClient.getPrivateNodeConfig().pipe(first()).subscribe(
        (res) => {
          this.defaultCredentials = res.default_credentials;
          this.isLoading = false;
        },
        error => {
          this.notifier.showError(
              'Failed to load private node config.',
              buildApiErrorMessage(error));
          this.isLoading = false;
        },
    );
  }

  /**
   * Triggered when import file button is clicked
   * On selecting a file, it will start to upload the file
   * @param keyFile The selected file
   */
  onKeyUpload(keyFile?: File) {
    this.isLoading = true;
    if (!keyFile) {
      return;
    }
    this.mttClient.setDefaultServiceAccount(keyFile)
        .pipe(delay(500))  // Delay for data to be persisted
        .subscribe(
            () => {
              this.notifier.showMessage(`Service account set`);
              this.isLoading = false;
              this.load();
            },
            error => {
              this.notifier.showError(
                  `Failed to set service account.`,
                  buildApiErrorMessage(error));
              this.isLoading = false;
            });
  }
}
