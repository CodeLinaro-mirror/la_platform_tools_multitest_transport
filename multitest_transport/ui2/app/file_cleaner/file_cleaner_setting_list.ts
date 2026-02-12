/**
 * Copyright 2021 Google LLC
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
import {finalize, takeUntil} from 'rxjs/operators';

import {MttClient} from '../services/mtt_client';
import {FileCleanerConfig, FileCleanerPolicy, FileCleanerSettings} from '../services/mtt_models';
import {Notifier} from '../services/notifier';
import {buildApiErrorMessage, deepCopy} from '../shared/util';

/** A component for displaying file cleaner settings. */
@Component({
  changeDetection: ChangeDetectionStrategy.Eager,standalone: false,
  selector: 'file-cleaner-setting-list',
  styleUrls: ['file_cleaner_setting_list.css'],
  templateUrl: './file_cleaner_setting_list.ng.html',
})
export class FileCleanerSettingList implements OnInit, OnDestroy {
  isLoading = false;
  settings: FileCleanerSettings = {};

  private readonly destroy = new ReplaySubject<void>();

  constructor(
      private readonly liveAnnouncer: LiveAnnouncer,
      private readonly mtt: MttClient, private readonly notifier: Notifier) {}

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

    this.mtt.getFileCleanerSettings()
        .pipe(takeUntil(this.destroy), finalize(() => {
                this.isLoading = false;
              }))
        .subscribe(
            settings => {
              this.settings = settings;
              this.liveAnnouncer.announce(
                  'File cleaner settings loaded', 'assertive');
            },
            error => {
              this.notifier.showError(
                  'Failed to load file cleaner settings.',
                  buildApiErrorMessage(error));
            },
        );
  }

  /** Delete a file cleaner policy after confirmation. */
  deletePolicy(policy: FileCleanerPolicy, i: number) {
    this.notifier
        .confirm(
            `Do you really want to delete file cleaner policy '${
                policy.name}'?`,
            'Delete policy')
        .subscribe(result => {
          if (!result) {
            return;
          }
          const updatedSettings = deepCopy(this.settings);
          updatedSettings.policies!.splice(i, 1);
          updatedSettings.configs?.forEach(config => {
            config.policy_names =
                config.policy_names?.filter(name => name !== policy.name);
          });
          this.mtt.updateFileCleanerSettings(updatedSettings)
              .subscribe(
                  () => {
                    this.settings = updatedSettings;
                    this.notifier.showMessage(
                        `File cleaner policy '${policy.name}' deleted.`);
                  },
                  error => {
                    this.load();
                    this.notifier.showError(
                        `Failed to delete file cleaner policy '${
                            policy.name}.'`,
                        buildApiErrorMessage(error));
                  },
              );
        });
  }

  /** Delete a file cleaner config after confirmation. */
  deleteConfig(config: FileCleanerConfig, i: number) {
    this.notifier
        .confirm(
            `Do you really want to delete file cleaner config '${
                config.name}'?`,
            'Delete config')
        .subscribe(result => {
          if (!result) {
            return;
          }
          const updatedSettings = deepCopy(this.settings);
          updatedSettings.configs!.splice(i, 1);
          this.mtt.updateFileCleanerSettings(updatedSettings)
              .subscribe(
                  () => {
                    this.settings = updatedSettings;
                    this.notifier.showMessage(
                        `File cleaner config '${config.name}' deleted.`);
                  },
                  error => {
                    this.load();
                    this.notifier.showError(
                        `Failed to delete file cleaner config '${
                            config.name}'.`,
                        buildApiErrorMessage(error));
                  },
              );
        });
  }

  /** Reset file cleaner settings after confirmation. */
  resetSettings() {
    this.notifier
        .confirm(
            'Do you really want to reset the File Cleaner settings to their' +
                ' default values?',
            'Reset settings')
        .subscribe(result => {
          if (!result) {
            return;
          }
          this.mtt.resetFileCleanerSettings().subscribe(
              () => {
                this.load();
                this.notifier.showMessage('File Cleaner settings reset.');
              },
              error => {
                this.notifier.showError(
                    'Failed to reset File Cleaner settings',
                    buildApiErrorMessage(error));
              },
          );
        });
  }
}
