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
import {FileCleanerCriterionType, FileCleanerPolicy, FileCleanerSettings, FileCleanerTargetType, initFileCleanerPolicy} from '../services/mtt_models';
import {Notifier} from '../services/notifier';
import {FormChangeTracker} from '../shared/can_deactivate';
import {buildApiErrorMessage} from '../shared/util';

/** Default file criterion type when adding a new criterion. */
const DEFAULT_CRITERION_TYPE = FileCleanerCriterionType.LAST_MODIFIED_TIME;

/** Edit page for file cleaner policy. */
@Component({
  selector: 'file-cleaner-policy-edit-page',
  styleUrls: ['file_cleaner_policy_edit_page.css'],
  templateUrl: './file_cleaner_policy_edit_page.ng.html',
})
export class FileCleanerPolicyEditPage extends FormChangeTracker implements
    OnInit {
  readonly TARGET_TYPES = Object.values(FileCleanerTargetType);

  editMode = false;
  data: Partial<FileCleanerPolicy> = initFileCleanerPolicy();
  settings: FileCleanerSettings = {};
  @ViewChild('backButton', {static: false}) backButton?: MatButton;
  @ViewChildren(FormChangeTracker)
  declare trackers: QueryList<FormChangeTracker>;
  existingPolicyNames = new Set<string>();

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
          this.settings.policies = this.settings.policies || [];
          this.existingPolicyNames.clear();
          for (const policy of this.settings.policies) {
            this.existingPolicyNames.add(policy.name);
          }

          const policy = this.settings.policies[i];
          if (policy) {
            this.editMode = true;
            this.existingPolicyNames.delete(policy.name);

            policy.target = policy.target || FileCleanerTargetType.FILE;
            policy.criteria = policy.criteria || [];
            // Init params to use the name-value-pair-list-form
            policy.operation.params = policy.operation.params || [];
            for (const criterion of policy.criteria) {
              criterion.params = criterion.params || [];
            }
            this.data = policy;
          }
        },
        error => {
          this.notifier.showError(
              'Failed to load file cleaner settings.',
              buildApiErrorMessage(error));
        });
  }

  onAddCriterion() {
    this.data.criteria!.push({
      type: DEFAULT_CRITERION_TYPE,
      params: [],
    });
  }

  onDeleteCriterion(i: number) {
    this.data.criteria!.splice(i, 1);
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
      this.settings.policies!.push({...this.data} as FileCleanerPolicy);
    }
    const msg = this.editMode ? 'update' : 'create';
    this.mtt.updateFileCleanerSettings(this.settings)
        .subscribe(
            () => {
              super.resetForm();
              this.back();
              this.notifier.showMessage(
                  `File cleaner policy '${this.data.name}' ${msg}d.`);
            },
            error => {
              this.notifier.showError(
                  `Failed to ${msg} file cleaner policy '${this.data.name}'.`,
                  buildApiErrorMessage(error));
            },
        );
  }
}
