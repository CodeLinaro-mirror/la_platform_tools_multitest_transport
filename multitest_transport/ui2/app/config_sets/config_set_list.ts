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
import {Component, Input, OnDestroy, OnInit} from '@angular/core';
import {ReplaySubject} from 'rxjs';
import {delay, finalize, first, takeUntil} from 'rxjs/operators';

import {MttClient} from '../services/mtt_client';
import {ConfigSetInfo, ConfigSetStatus} from '../services/mtt_models';
import {Notifier} from '../services/notifier';
import {buildApiErrorMessage} from '../shared/util';

/** A component for displaying a list of imported config sets. */
@Component({
  standalone: false,
  selector: 'config-set-list',
  styleUrls: ['config_set_list.css'],
  templateUrl: './config_set_list.ng.html',
})
export class ConfigSetList implements OnInit, OnDestroy {
  isLoading = false;
  infoMap: {[id: string]: ConfigSetInfo} = {};
  infoStatusLoadingSet = new Set<string>();
  readonly ConfigSetStatus = ConfigSetStatus;
  readonly Object = Object;

  private readonly destroy = new ReplaySubject<void>();

  @Input()
  displayedColumns: string[] = [
    'name',
    'description',
    'status',
    'actions',
  ];

  constructor(
      private readonly mttClient: MttClient,
      private readonly notifier: Notifier,
      private readonly liveAnnouncer: LiveAnnouncer,
  ) {}

  ngOnInit() {
    this.load();
  }

  ngOnDestroy() {
    this.destroy.next();
    this.liveAnnouncer.clear();
  }

  load() {
    this.isLoading = true;
    this.liveAnnouncer.announce('Loading config sets', 'polite');

    this.mttClient
        .getConfigSetInfos(
            /* includeRemote */ false,
            [ConfigSetStatus.IMPORTED, ConfigSetStatus.UPDATABLE])
        .pipe(
            takeUntil(this.destroy),
            finalize(() => {
              this.isLoading = false;
            }),
            )
        .subscribe(
            infoListRes => {
              this.liveAnnouncer.announce('Config set loaded', 'assertive');

              for (const info of infoListRes.config_set_infos || []) {
                this.infoMap[info.url] = info;
                this.getLatestVersion(info);
              }
            },
            error => {
              this.notifier.showError(
                  'Failed to load config sets.', buildApiErrorMessage(error));
            },
        );
  }

  getLatestVersion(importedInfo: ConfigSetInfo) {
    this.infoStatusLoadingSet.add(importedInfo.url);
    this.mttClient.configSets.getLatestVersion(importedInfo)
        .pipe(finalize(() => {
          this.infoStatusLoadingSet.delete(importedInfo.url);
        }))
        .subscribe(
            infoRes => {
              this.infoMap[infoRes.url] = infoRes;
            },
            error => {  // Ignore urls that weren't found
              console.log(
                  `No remote config set found for url: ${importedInfo.url}`);
            });
  }

  /**
   * Triggered when import file button is clicked
   * On selecting a file, it will start to upload the file
   * @param file The selected file
   */
  onConfigSetFileUpload(file?: File) {
    if (!file) {
      return;
    }

    const reader = new FileReader();
    this.isLoading = true;
    this.liveAnnouncer.announce('Importing config set', 'polite');

    reader.onloadend = () => {
      // import file contents
      const content = reader.result as string;

      if (!content) {
        this.notifier.showError(`Failed to import file with empty content`);
        return;
      }

      this.mttClient.importConfigSet('', content)
          .pipe(
              first(),
              delay(100),  // Wait for updates
              finalize(() => {
                this.isLoading = false;
              }),
              )
          .subscribe(
              result => {
                this.notifier.showMessage(`Config set imported`);
                this.load();
              },
              error => {
                this.notifier.showError(
                    'Failed to import config set.',
                    buildApiErrorMessage(error));
              });
    };
    // read contents
    reader.readAsText(file);
  }

  updateConfigSet(info: ConfigSetInfo) {
    this.isLoading = true;
    this.liveAnnouncer.announce('Updating config set', 'polite');

    this.mttClient.importConfigSet(info.url)
        .pipe(
            first(),
            delay(100),
            finalize(() => {
              this.isLoading = false;
            }),
            )
        .subscribe(
            result => {
              this.notifier.showMessage('Config set updated');
              this.load();
            },
            error => {
              this.notifier.showError(
                  'Failed to update config set.', buildApiErrorMessage(error));
            });
  }

  deleteConfigSet(info: ConfigSetInfo) {
    this.notifier
        .confirm(
            `Do you really want to remove the '${
                info.name}' config set? This will also remove all corresponding test suites and actions.`,
            'Remove config set')
        .subscribe(result => {
          if (!result) {
            return;
          }
          this.isLoading = true;
          this.mttClient.deleteConfigSet(info.url)
              .pipe(
                  first(),
                  delay(100),
                  )
              .subscribe(
                  result => {
                    this.notifier.showMessage(
                        `${info.name} config set removed`);
                    this.load();
                    // Let load() set isLoading = false
                  },
                  error => {
                    this.notifier.showError(
                        `Failed to remove ${info.name} config set.`,
                        buildApiErrorMessage(error));
                    this.isLoading = false;
                  });
        });
  }
}
