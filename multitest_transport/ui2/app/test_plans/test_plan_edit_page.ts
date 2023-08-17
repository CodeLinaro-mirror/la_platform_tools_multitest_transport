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
import {COMMA, ENTER} from '@angular/cdk/keycodes';
import {AfterViewInit, Component, OnDestroy, OnInit, ViewChild} from '@angular/core';
import {MatButton} from '@angular/material/button';
import {MatChipInputEvent} from '@angular/material/chips';
import {MatStepper} from '@angular/material/stepper';
import {ActivatedRoute, Params, Router} from '@angular/router';
import {forkJoin, of as observableOf, ReplaySubject, Subscription} from 'rxjs';
import {first} from 'rxjs/operators';

import {TestResourceClassType, TestResourceForm} from '../build_channels/test_resource_form';
import {MttClient} from '../services/mtt_client';
import * as mttModels from '../services/mtt_models';
import {Notifier} from '../services/notifier';
import {FormChangeTracker} from '../shared/can_deactivate';
import {buildApiErrorMessage, resetStepCompletion} from '../shared/util';

enum Step {
  CONFIGURE_TEST_PLAN = 0,
  CONFIGURE_TEST_RUN = 1,
  ADD_DEVICE_ACTIONS = 2,
  SET_TEST_RESOURCES = 3
}
const TOTAL_STEPS = 4;

/**
 * Form for creating or editing a test plan
 */
@Component({
  selector: 'test-plan-edit-page',
  styleUrls: ['test_plan_edit_page.css'],
  templateUrl: './test_plan_edit_page.ng.html',
})
export class TestPlanEditPage extends FormChangeTracker implements
    OnDestroy, OnInit, AfterViewInit {
  @ViewChild('backButton', {static: false}) backButton?: MatButton;

  // Validation variables
  @ViewChild(TestResourceForm, {static: true})
  testResourceForm!: TestResourceForm;
  errorMessage = '';

  // Record each step whether it has finished or not
  stepCompletionStatusMap: {[stepNum: number]: boolean} = {};
  step = Step;
  totalSteps = TOTAL_STEPS;

  data: Partial<mttModels.TestPlan> = mttModels.initTestPlan();

  selectedDeviceActions: mttModels.DeviceAction[] = [];
  selectedTestRunActions: mttModels.TestRunAction[] = [];

  editMode = false;
  nodeConfigTestResourceUrls: mttModels.NameValuePair[] = [];
  testResourceClassType = TestResourceClassType;
  testResourceObjs: mttModels.TestResourceObj[] = [];

  /** Keys used to separate labels */
  readonly separatorKeyCodes: number[] = [ENTER, COMMA];

  isLoading = false;
  deviceInfoSubscription?: Subscription;

  private readonly destroy = new ReplaySubject<void>(1);

  constructor(
      private readonly liveAnnouncer: LiveAnnouncer,
      private readonly mttClient: MttClient,
      private readonly notifier: Notifier,
      private readonly route: ActivatedRoute,
      private readonly router: Router,
  ) {
    super();
  }

  ngOnInit() {
    this.route.params.pipe(first()).subscribe((params: Params) => {
      this.loadData(params['id']);
    });

    // Initialize step completion status map
    resetStepCompletion(0, this.stepCompletionStatusMap, this.totalSteps);
  }

  ngOnDestroy() {
    this.destroy.next();
    this.destroy.complete();
  }

  /**
   * Triggered on click next button in stepper
   * @param stepper MatStepper
   */
  goForward(stepper: MatStepper): void {
    if (this.validateStep(stepper.selectedIndex)) {
      this.stepCompletionStatusMap[stepper.selectedIndex] = true;
      // wait for data to populate stepper
      setTimeout(() => {
        stepper.next();
      }, 100);
    }
  }

  /**
   * Validate each step and populate error messages
   * @param currentStep Indicate which step are we validating
   */
  validateStep(currentStep: Step): boolean {
    this.errorMessage = '';
    this.invalidInputs = [];
    switch (currentStep) {
      case Step.CONFIGURE_TEST_PLAN: {
        this.invalidInputs = this.getInvalidInputs();
        return !this.invalidInputs.length;
      }
      case Step.CONFIGURE_TEST_RUN: {
        const res = !!this.data.test_run_sequences &&
            !!this.data.test_run_sequences.length;
        if (!res) {
          this.errorMessage = 'Test run configuration is required';
        }
        return res;
      }
      default: {
        break;
      }
    }
    return true;
  }

  onStepperSelectionChange(selectedIndex: number) {
    resetStepCompletion(
        selectedIndex, this.stepCompletionStatusMap, this.totalSteps);
  }

  ngAfterViewInit() {
    this.backButton!.focus();
  }

  loadData(testPlanId: string|undefined) {
    this.editMode = !!testPlanId;
    if (this.editMode) {
      this.isLoading = true;
      this.liveAnnouncer.announce('Loading', 'polite');
    }

    const nodeConfigObs = this.mttClient.getNodeConfig();
    const testPlanObs = testPlanId ? this.mttClient.getTestPlan(testPlanId) :
                                     observableOf(null);

    // Get API call results
    forkJoin({
      nodeConfig: nodeConfigObs,
      testPlan: testPlanObs,
    })
        .pipe(first())
        .subscribe(
            (res) => {
              // Node Configs
              this.nodeConfigTestResourceUrls =
                  res.nodeConfig.test_resource_default_download_urls || [];

              // Test Plan
              this.loadTestPlan(res.testPlan);

              if (this.editMode) {
                this.isLoading = false;
                this.liveAnnouncer.announce('Test plan loaded', 'assertive');
              }
            },
            (error) => {
              this.notifier.showError(
                  'Failed to load test plan.', buildApiErrorMessage(error));
            });
  }

  loadTestPlan(testPlan: mttModels.TestPlan|null) {
    if (!testPlan) {
      return;
    }

    this.data = testPlan;
    this.data.cron_exp = testPlan.cron_exp || '';
    this.data.before_device_action_ids =
        testPlan.before_device_action_ids || [];
    this.data.labels = testPlan.labels || [];
    this.data.test_resource_pipes = testPlan.test_resource_pipes || [];
  }

  addLabel(event: MatChipInputEvent) {
    const input = event.chipInput.inputElement;
    const value = event.value;

    if ((value || '').trim() &&
        this.data.labels!.indexOf(value.trim()) === -1) {
      this.data.labels!.push(value.trim());
    }

    if (input) {
      input.value = '';
    }
  }

  removeLabel(label: string) {
    const index = this.data.labels!.indexOf(label);
    if (index >= 0) {
      this.data.labels!.splice(index, 1);
    }
  }

  updateConfigSequenceList(sequences: mttModels.TestRunSequence[]) {
    this.data.test_run_sequences = sequences;
  }

  back() {
    this.router.navigate(['test_plans']);
  }

  // create or update test plan
  submit() {
    if (!this.validateStep(Step.CONFIGURE_TEST_RUN)) {
      return;
    }

    const resultTest: mttModels.TestPlan = {
      id: this.data.id,
      name: this.data.name!.trim(),
      labels: this.data.labels,
      cron_exp: this.data.cron_exp!.trim(),
      cron_exp_timezone: this.data.cron_exp_timezone,
      test_run_configs: [],
      test_run_sequences: this.data.test_run_sequences,
    };

    if (this.editMode) {
      this.mttClient.updateTestPlan(resultTest.id!, resultTest)
          .subscribe(
              () => {
                super.resetForm();
                this.back();
                this.notifier.showMessage(
                    `Test plan '${resultTest.name}' updated`);
              },
              (error) => {
                this.notifier.showError(
                    'Failed to update test plan.', buildApiErrorMessage(error));
              });
    } else {
      this.mttClient.createTestPlan(resultTest)
          .subscribe(
              () => {
                super.resetForm();
                this.back();
                this.notifier.showMessage(
                    `Test plan '${resultTest.name}' created`);
              },
              (error) => {
                this.notifier.showError(
                    'Failed to create test plan.', buildApiErrorMessage(error));
              });
    }
  }
}
