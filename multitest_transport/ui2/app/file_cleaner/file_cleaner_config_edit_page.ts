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

import {Component, OnInit, QueryList, ViewChild, ViewChildren} from '@angular/core';
import {MatButton} from '@angular/material/button';
import {ActivatedRoute, Params, Router} from '@angular/router';

import {MttClient} from '../services/mtt_client';
import {FileCleanerConfig, FileCleanerSettings, initFileCleanerConfig} from '../services/mtt_models';
import {Notifier} from '../services/notifier';
import {FormChangeTracker} from '../shared/can_deactivate';
import {buildApiErrorMessage} from '../shared/util';

/** Edit page for file cleaner config. */
@Component({
  standalone: false,
  selector: 'file-cleaner-config-edit-page',
  styleUrls: ['file_cleaner_config_edit_page.css'],
  templateUrl: './file_cleaner_config_edit_page.ng.html',
})
export class FileCleanerConfigEditPage extends FormChangeTracker implements
    OnInit {
  editMode = false;
  data: Partial<FileCleanerConfig> = initFileCleanerConfig();
  settings: FileCleanerSettings = {};
  policyNames = new Set<string>();
  @ViewChild('backButton', {static: false}) backButton?: MatButton;
  @ViewChildren(FormChangeTracker)
  declare trackers: QueryList<FormChangeTracker>;

  constructor(
      private readonly mtt: MttClient, private readonly notifier: Notifier,
      private readonly route: ActivatedRoute, private readonly router: Router) {
    super();
  }

  ngOnInit() {
    this.route.params.subscribe((params: Params) => {
      this.load(params['index']);
    });
  }

  ngAfterViewInit() {
    this.backButton!.focus();
  }

  load(i: number) {
    this.mtt.getFileCleanerSettings().subscribe(
        settings => {
          this.settings = settings;
          this.settings.configs = this.settings.configs || [];
          this.policyNames.clear();
          settings.policies?.forEach((policy) => {
            this.policyNames.add(policy.name);
          });

          const config = this.settings.configs[i];
          if (config) {
            this.editMode = true;

            config.directories = config.directories || [];
            // Remove policy names which are not in setting.policies
            const policies =
                config.policy_names?.filter(name => this.policyNames.has(name));
            config.policy_names = policies || [];
            this.data = config;
          }
        },
        error => {
          this.notifier.showError(
              'Failed to load file cleaner settings.',
              buildApiErrorMessage(error));
        });
  }

  onAddDirectory() {
    this.data.directories!.push('');
  }

  onDeleteDirectory(i: number) {
    this.data.directories!.splice(i, 1);
  }

  onAddPolicyName() {
    this.data.policy_names!.push('');
  }

  onDeletePolicyName(i: number) {
    this.data.policy_names!.splice(i, 1);
  }

  back() {
    this.router.navigate(['/', 'settings', 'file_cleaner']);
  }

  validateForm(): boolean {
    this.invalidInputs = this.getInvalidInputs();
    for (const tracker of this.trackers) {
      this.invalidInputs.push(...tracker.getInvalidInputs());
    }
    return !this.invalidInputs.length;
  }

  onSubmit() {
    if (!this.validateForm()) {
      return;
    }

    if (!this.editMode) {
      this.settings.configs!.push({...this.data} as FileCleanerConfig);
    }
    const msg = this.editMode ? 'update' : 'create';
    this.mtt.updateFileCleanerSettings(this.settings)
        .subscribe(
            () => {
              super.resetForm();
              this.back();
              this.notifier.showMessage(
                  `File cleaner config '${this.data.name}' ${msg}d.`);
            },
            error => {
              this.notifier.showError(
                  `Failed to ${msg} file cleaner config '${this.data.name}'.`,
                  buildApiErrorMessage(error));
            },
        );
  }
}
