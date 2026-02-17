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
import {Component, OnDestroy, OnInit, QueryList, ViewChildren, ChangeDetectionStrategy} from '@angular/core';
import {forkJoin, ReplaySubject} from 'rxjs';
import {finalize, first, takeUntil} from 'rxjs/operators';

import {MttClient} from '../services/mtt_client';
import {NodeConfig, PrivateNodeConfig} from '../services/mtt_models';
import {Notifier} from '../services/notifier';
import {FormChangeTracker} from '../shared/can_deactivate';
import {NameValuePairListForm} from '../shared/name_value_pair_list_form';
import {buildApiErrorMessage} from '../shared/util';

/** A component for displaying setting form */
@Component({
  changeDetection: ChangeDetectionStrategy.Eager,standalone: false,
  selector: 'setting-form',
  styleUrls: ['setting_form.css'],
  templateUrl: './setting_form.ng.html',
})
export class SettingForm extends FormChangeTracker implements OnInit,
                                                              OnDestroy {
  @ViewChildren(NameValuePairListForm)
  nameValuePairListForms!: QueryList<NameValuePairListForm>;

  isLoading = false;
  constructor(
      private readonly notifier: Notifier,
      private readonly mtt: MttClient,
      private readonly liveAnnouncer: LiveAnnouncer,
  ) {
    super();
  }
  nodeConfig!: Partial<NodeConfig>;
  privateNodeConfig: PrivateNodeConfig = {};
  private readonly destroy = new ReplaySubject<void>();

  ngOnInit() {
    this.load();
  }

  ngOnDestroy() {
    this.destroy.next();
    this.liveAnnouncer.clear();
  }

  load() {
    const nodeConfigObs = this.mtt.getNodeConfig();
    const privateNodeConfigObs = this.mtt.getPrivateNodeConfig();

    this.isLoading = true;
    this.liveAnnouncer.announce('Loading', 'polite');

    forkJoin([nodeConfigObs, privateNodeConfigObs])
        .pipe(
            takeUntil(this.destroy),
            finalize(() => {
              this.isLoading = false;
            }),
            )
        .subscribe(
            ([nodeConfigRes, privateNodeConfigRes]) => {
              this.nodeConfig = nodeConfigRes;
              this.nodeConfig.env_vars = nodeConfigRes.env_vars || [];
              this.nodeConfig.test_resource_default_download_urls =
                  nodeConfigRes.test_resource_default_download_urls || [];

              this.privateNodeConfig = privateNodeConfigRes;
              this.privateNodeConfig.metrics_enabled =
                  privateNodeConfigRes.metrics_enabled || false;
              this.privateNodeConfig.setup_wizard_completed =
                  privateNodeConfigRes.setup_wizard_completed || false;
              this.liveAnnouncer.announce('Settings loaded', 'assertive');
            },
            error => {
              this.notifier.showError(
                  'Failed to load settings.', buildApiErrorMessage(error));
            },
        );
  }

  onAddDefaultDownloadUrls() {
    this.nodeConfig.test_resource_default_download_urls!.push({name: ''});
  }

  onAddEnvironmentVariable() {
    this.nodeConfig.env_vars!.push({name: ''});
  }

  onRemoveDefaultDownloadUrls(i: number) {
    this.nodeConfig.test_resource_default_download_urls!.splice(i, 1);
  }

  onRemoveEnvironmentVariable(i: number) {
    this.nodeConfig.env_vars!.splice(i, 1);
  }

  /**
   * Validate Form
   * @return boolean. True if form is valid, false otherwise.
   */
  validateForm() {
    this.invalidInputs = [];
    for (const form of this.nameValuePairListForms) {
      this.invalidInputs = this.invalidInputs.concat(form.getInvalidInputs());
    }
    return !this.invalidInputs.length;
  }

  onSubmit() {
    if (!this.validateForm()) {
      return;
    }
    const resultNodeConfig: NodeConfig = {...this.nodeConfig} as NodeConfig;

    const nodeConfigObs = this.mtt.updateNodeConfig(resultNodeConfig);
    const privateNodeConfigObs =
        this.mtt.updatePrivateNodeConfig(this.privateNodeConfig);

    forkJoin([nodeConfigObs, privateNodeConfigObs])
        .pipe(first())
        .subscribe(
            result => {
              super.resetForm();
              this.notifier.showMessage('Settings updated');
            },
            error => {
              this.notifier.showError(
                  'Failed to update settings.', buildApiErrorMessage(error));
            },
        );
  }
}
