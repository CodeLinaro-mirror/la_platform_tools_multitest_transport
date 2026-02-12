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
import {Component, ChangeDetectionStrategy} from '@angular/core';

import {MttClient} from '../services/mtt_client';
import {Notifier} from '../services/notifier';
import {buildApiErrorMessage} from '../shared/util';

/** A component for restore a backup config exported from an MTT instance. */
@Component({
  changeDetection: ChangeDetectionStrategy.Eager,standalone: false,
  selector: 'config-restore-step',
  styleUrls: ['config_restore_step.css'],
  templateUrl: './config_restore_step.ng.html',
})
export class ConfigRestoreStep {
  isLoading = false;

  constructor(
      private readonly mttClient: MttClient,
      private readonly notifier: Notifier,
      private readonly liveAnnouncer: LiveAnnouncer) {}

  /**
   * Triggered when import file button is clicked
   * On selecting a file, it will start to upload the file
   * @param file The selected file
   */
  onConfigBackupUpload(file?: File) {
    if (!file) {
      return;
    }

    const reader = new FileReader();
    this.isLoading = true;
    this.liveAnnouncer.announce('Restoring configs', 'polite');

    reader.onloadend = () => {
      // Import file contents
      const content = reader.result as string;

      if (!content) {
        this.notifier.showError(`Failed to restore config with empty content`);
        return;
      }

      this.mttClient.importNodeConfig(content).subscribe(
          result => {
            // TODO: move to next step after importing
            this.notifier.showMessage(`Config restored`);
            this.isLoading = false;
            this.liveAnnouncer.announce('Config restored', 'assertive');
          },
          error => {
            this.notifier.showError(
                'Failed to restore config.', buildApiErrorMessage(error));
            this.isLoading = false;
          });
    };
    // Read contents
    reader.readAsText(file);
  }
}
