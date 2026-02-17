/**
 * Copyright 2019 Google LLC
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
import {Component, Input, OnDestroy, OnInit, ChangeDetectionStrategy} from '@angular/core';
import {ReplaySubject} from 'rxjs';
import {delay, finalize, takeUntil} from 'rxjs/operators';

import {MttClient} from '../services/mtt_client';
import {ConfigSetInfo, ConfigSetStatus, getNamespaceFromId, Test} from '../services/mtt_models';
import {MttObjectMapService} from '../services/mtt_object_map';
import {Notifier} from '../services/notifier';
import {buildApiErrorMessage} from '../shared/util';

/** A component for displaying a list of test runs. */
@Component({
  changeDetection: ChangeDetectionStrategy.Eager,standalone: false,
  selector: 'test-list',
  styleUrls: ['test_list.css'],
  templateUrl: './test_list.ng.html',
})
export class TestList implements OnInit, OnDestroy {
  @Input() columnsToDisplay = ['name', 'description', 'actions'];

  isLoading = false;
  testsByNamespaceMap: {[namespace: string]: Test[]} = {};
  configSetInfoMap: {[url: string]: ConfigSetInfo} = {};

  private readonly destroy = new ReplaySubject<void>();

  constructor(
      private readonly mttClient: MttClient,
      private readonly mttObjectMapService: MttObjectMapService,
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
    this.liveAnnouncer.announce('Loading', 'polite');

    this.mttObjectMapService.getMttObjectMap(true /* forceUpdate */)
        .pipe(
            takeUntil(this.destroy),
            finalize(() => {
              this.isLoading = false;
            }),
            )
        .subscribe(
            objectMap => {
              this.configSetInfoMap = objectMap.configSetInfoMap;
              this.testsByNamespaceMap = {};

              for (const test of Object.values(objectMap.testMap)) {
                const namespace = getNamespaceFromId(test.id || '');
                if (!(namespace in this.testsByNamespaceMap)) {
                  this.testsByNamespaceMap[namespace] = [];
                }
                this.testsByNamespaceMap[namespace].push(test);
              }

              this.getLatestConfigSetInfos();

              this.liveAnnouncer.announce('Tests loaded', 'assertive');
            },
            error => {
              this.notifier.showError(
                  'Failed to get test suites.', buildApiErrorMessage(error));
            },
        );
  }

  isNamespaceSectionEditable(namespace: string): boolean {
    return !namespace || !(namespace in this.configSetInfoMap);
  }

  getNamespaceTitle(namespace: string): string {
    if (!namespace) {
      return 'Default/Custom Test Suites';
    }
    if (namespace in this.configSetInfoMap) {
      return this.configSetInfoMap[namespace].name;
    }
    return `Unknown Config Set (${namespace})`;
  }

  deleteTest(test: Test) {
    this.notifier
        .confirm(
            `Do you really want to delete test '${test.name}'?`, 'Delete test')
        .subscribe(result => {
          if (!result) {
            return;
          }
          this.mttClient.deleteTest(test.id!).subscribe(
              () => {
                this.notifier.showMessage(`Test '${test.name}' deleted`);
                this.load();
              },
              error => {
                this.notifier.showError(
                    `Failed to delete ${test.name}`,
                    buildApiErrorMessage(error));
              });
        });
  }

  getLatestConfigSetInfos() {
    // Checks if any config sets can be updated and updates the status in map
    for (const [url, info] of Object.entries(this.configSetInfoMap)) {
      this.mttClient.configSets.getLatestVersion(info).subscribe(
          infoRes => {
            this.configSetInfoMap[url] = infoRes;
          },
          error => {
            console.log(
                `Failed to check updates for config set ${url}: ${error}`);
          });
    }
  }

  isConfigSetUpdatable(namespace: string) {
    const info = this.configSetInfoMap[namespace];
    return info && info.status === ConfigSetStatus.UPDATABLE;
  }

  updateConfigSet(namespace: string) {
    this.isLoading = true;
    this.liveAnnouncer.announce('Updating config set', 'assertive');

    this.mttClient.importConfigSet(namespace)
        .pipe(delay(100))  // Wait for updates before reloading
        .pipe(finalize(() => {
          this.isLoading = false;
          this.liveAnnouncer.announce('Config set updated');
          this.load();
        }))
        .subscribe(
            result => {
              this.notifier.showMessage(`Config set ${namespace} updated`);
            },
            error => {
              this.notifier.showError(
                  'Failed to update config set ${namespace}',
                  buildApiErrorMessage(error));
            });
  }

  confirmDeleteConfigSet(namespace: string) {
    const configSetName = this.getNamespaceTitle(namespace);
    // TODO: List affected tests/actions
    this.notifier
        .confirm(
            `Do you really want to delete config set '${
                configSetName}'? This will remove all test suites and actions` +
                ` associated with the config set.`,
            'Delete config set')
        .subscribe(result => {
          if (!result) {
            return;
          }
          this.deleteConfigSet(namespace);
        });
  }

  deleteConfigSet(namespace: string) {
    const configSetName = this.getNamespaceTitle(namespace);
    this.mttClient.deleteConfigSet(namespace).subscribe(
        () => {
          this.notifier.showMessage(`Config set '${configSetName}' deleted`);
          this.load();
        },
        error => {
          this.notifier.showError(
              `Failed to delete config set ${configSetName}`,
              buildApiErrorMessage(error));
        });
  }
}
