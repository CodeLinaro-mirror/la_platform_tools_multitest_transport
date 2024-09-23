/**
 * Copyright 2022 Google LLC
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

import {AfterViewInit, Component, OnInit, QueryList, ViewChild, ViewChildren} from '@angular/core';
import {MatButton} from '@angular/material/button';
import {ActivatedRoute, Router} from '@angular/router';
import {forkJoin, of as observableOf} from 'rxjs';
import {first} from 'rxjs/operators';

import {MttClient} from '../services/mtt_client';
import {newTestRunAction, TestRunAction, TestRunHook, TestRunPhase} from '../services/mtt_models';
import {Notifier} from '../services/notifier';
import {FormChangeTracker} from '../shared/can_deactivate';
import {buildApiErrorMessage} from '../shared/util';

/**
 * Form for creating a test run action
 */
@Component({
  standalone: false,
  selector: 'test-run-action-edit-page',
  styleUrls: ['test_run_action_edit_page.css'],
  templateUrl: './test_run_action_edit_page.ng.html',
})
export class TestRunActionEditPage extends FormChangeTracker implements
    OnInit, AfterViewInit {
  readonly PHASES = Object.values(TestRunPhase).slice(1);
  readonly Object = Object;

  isLoading = false;
  editMode = false;
  data: Partial<TestRunAction> = newTestRunAction();
  testRunHookMap: {[key: string]: TestRunHook} = {};

  @ViewChild('backButton', {static: false}) backButton?: MatButton;
  @ViewChildren(FormChangeTracker)
  declare trackers: QueryList<FormChangeTracker>;

  constructor(
      private readonly mttClient: MttClient,
      private readonly notifier: Notifier,
      private readonly route: ActivatedRoute, private readonly router: Router) {
    super();
  }

  ngOnInit() {
    this.route.params.pipe(first()).subscribe(params => {
      this.loadData(params['id'] || params['copy_id']);
    });
  }

  ngAfterViewInit() {
    this.backButton!.focus();
  }

  loadData(id?: string) {
    this.isLoading = true;
    this.editMode = !!id;
    const testRunActionObs =
        id ? this.mttClient.testRunActions.get(id) : observableOf(null);
    const testRunHookObs = this.mttClient.testRunActions.listTestRunHooks();
    forkJoin([testRunActionObs, testRunHookObs])
        .pipe()
        .subscribe(
            ([testRunActionRes, testRunHookRes]) => {
              if (testRunActionRes) {
                this.data = testRunActionRes;
                this.data.phases = testRunActionRes.phases || [];
                this.data.options = testRunActionRes.options || [];
                this.data.tradefed_result_reporters =
                    testRunActionRes.tradefed_result_reporters || [];
                if (!this.editMode) {
                  // Clear ID to ensure a new test run action is created
                  delete this.data.id;
                  this.data.name = `${this.data.name} (copy)`;
                }
              }
              testRunHookRes.test_run_hooks?.reduce((map, hook) => {
                map[hook.name] = hook;
                return map;
              }, this.testRunHookMap);
              this.isLoading = false;
            },
            error => {
              this.notifier.showError(
                  `Failed to load test run action '${id}'`,
                  buildApiErrorMessage(error));
            },
        );
  }

  onSelectTestRunHook(hookName: string) {
    const testRunHook = this.testRunHookMap[hookName];
    if (testRunHook) {
      this.data.options =
          testRunHook.option_defs?.map(optionDef => ({
                                         name: optionDef.name,
                                         value: optionDef.default || '',
                                       })) ||
          [];
    }
  }

  onAddOption() {
    this.data.options!.push({name: '', value: ''});
  }

  onRemoveOption(i: number) {
    this.data.options!.splice(i, 1);
  }

  onAddResultReporter() {
    this.data.tradefed_result_reporters!.push(
        {class_name: '', option_values: []});
  }

  onDeleteResultReporter(index: number) {
    this.data.tradefed_result_reporters!.splice(index, 1);
  }

  back() {
    this.router.navigate(['/', 'settings', 'test_run_actions']);
  }

  validate(): boolean {
    this.invalidInputs = this.getInvalidInputs();
    for (const tracker of this.trackers) {
      this.invalidInputs.push(...tracker.getInvalidInputs());
    }
    return !this.invalidInputs.length;
  }

  onSubmit() {
    if (!this.validate()) {
      return;
    }
    const resultTestRunAction: TestRunAction = {...this.data} as TestRunAction;
    if (this.editMode) {
      this.mttClient.testRunActions
          .update(resultTestRunAction.id, resultTestRunAction)
          .pipe(first())
          .subscribe(
              () => {
                // Reset form state, because we prevent dirty forms from
                // navigating away
                super.resetForm();
                this.back();
                this.notifier.showMessage(
                    `Test run action '${resultTestRunAction.name}' updated`);
              },
              error => {
                this.notifier.showError(
                    `Failed to update test run action '${
                        resultTestRunAction.name}'.`,
                    buildApiErrorMessage(error));
              },
          );
    } else {
      this.mttClient.testRunActions.create(resultTestRunAction)
          .pipe(first())
          .subscribe(
              () => {
                // Reset form state, because we prevent dirty forms from
                // navigating away
                super.resetForm();
                this.back();
                this.notifier.showMessage(
                    `Test run action '${resultTestRunAction.name}' created`);
              },
              error => {
                this.notifier.showError(
                    `Failed to create test run action '${
                        resultTestRunAction.name}'.`,
                    buildApiErrorMessage(error));
              },
          );
    }
  }
}
