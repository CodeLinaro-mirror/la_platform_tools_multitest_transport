/**
 * Copyright 2023 Google LLC
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
import {Component, EventEmitter, Inject, OnDestroy, OnInit, Output, ViewChild} from '@angular/core';
import {MAT_DIALOG_DATA, MatDialogRef} from '@angular/material/dialog';
import {MatStepper} from '@angular/material/stepper';
import {forkJoin, ReplaySubject} from 'rxjs';
import {finalize, takeUntil} from 'rxjs/operators';

import {TestResourceClassType, TestResourceForm} from '../build_channels/test_resource_form';
import {MttClient} from '../services/mtt_client';
import * as mttModels from '../services/mtt_models';
import {Notifier} from '../services/notifier';
import {FormChangeTracker} from '../shared/can_deactivate';
import {buildApiErrorMessage, resetStepCompletion} from '../shared/util';

/**
 * Data format when passed to XtsRequirementDetect
 * @param testRunConfig target config to edit.
 */
export interface XtsRequirementDetectData {
  testRunConfig: Partial<mttModels.TestRunConfig>;
}

enum Step {
  SELECT_RUN_TARGETS = 0,
  SET_TEST_RESOURCES = 1,
}
const TOTAL_STEPS = 2;

/**
 * This component is used to set up xTS requirement detection config.
 */
@Component({
  selector: 'xts-requirement-detect',
  styleUrls: ['xts_requirement_detect.css'],
  templateUrl: './xts_requirement_detect.ng.html',
  providers: [{provide: FormChangeTracker, useExisting: XtsRequirementDetect}]
})
export class XtsRequirementDetect extends FormChangeTracker implements
    OnInit, OnDestroy {
  @ViewChild(TestResourceForm, {static: false})
  testResourceForm!: TestResourceForm;

  @Output()
  readonly configSubmitted = new EventEmitter<mttModels.TestRunConfig>();

  isLoading = false;
  // Record each step whether it has finished or not.
  stepCompletionStatusMap: {[stepNum: number]: boolean} = {};
  // Validation variable.
  errorMessage = '';
  buildChannels: mttModels.BuildChannel[] = [];

  readonly deviceWarningMessage =
      'Select a device that has been flashed with the build.';
  readonly resetStepCompletion = resetStepCompletion;
  readonly Step = Step;
  readonly TestResourceClassType = TestResourceClassType;
  readonly TOTAL_STEPS = TOTAL_STEPS;

  private readonly destroy = new ReplaySubject<void>();

  constructor(
      @Inject(MAT_DIALOG_DATA) public data: XtsRequirementDetectData,
      private readonly dialogRef: MatDialogRef<XtsRequirementDetect>,
      private readonly liveAnnouncer: LiveAnnouncer,
      private readonly mttClient: MttClient,
      private readonly notifier: Notifier) {
    super();
    // When user clicked outside of the dialog, close the dialog.
    dialogRef.backdropClick().subscribe(() => {
      this.dialogRef.close();
    });
  }

  ngOnInit() {
    this.resetStepCompletion(0, this.stepCompletionStatusMap, TOTAL_STEPS);
    this.load();
  }

  ngOnDestroy() {
    this.destroy.next();
    this.liveAnnouncer.clear();
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
   * On submit test run config, close the dialog.
   */
  submit() {
    if (!this.validateStep(Step.SET_TEST_RESOURCES)) {
      return;
    }

    this.configSubmitted.emit(
        this.data.testRunConfig as mttModels.TestRunConfig);
    this.dialogRef.close();
  }

  private load() {
    this.isLoading = true;
    this.liveAnnouncer.announce('Loading', 'polite');

    forkJoin([
      this.mttClient.getTest(this.data.testRunConfig.test_id!),
      this.mttClient.getBuildChannels()
    ])
        .pipe(
            takeUntil(this.destroy),
            finalize(() => {
              this.isLoading = false;
            }),
            )
        .subscribe(
            ([testRes, buildChannelRes]) => {
              this.data.testRunConfig.test_resource_objs =
                  testRes.test_resource_defs?.map(
                      def => mttModels.testResourceDefToObj(def)) ||
                  [];
              this.buildChannels = buildChannelRes.build_channels || [];
              this.liveAnnouncer.announce('Tests loaded', 'assertive');
            },
            error => {
              this.notifier.showError(
                  'Failed to get data.', buildApiErrorMessage(error));
            },
        );
  }

  /**
   * Validate each step and populate error messages
   * @param currentStep Indicate which step are we validating
   */
  private validateStep(currentStep: Step): boolean {
    this.errorMessage = '';
    this.invalidInputs = [];
    switch (currentStep) {
      case Step.SELECT_RUN_TARGETS: {
        const res = !!this.data.testRunConfig.device_specs &&
            0 < this.data.testRunConfig.device_specs.length;
        if (!res) {
          this.errorMessage = 'Device spec is required';
        }
        return res;
      }
      case Step.SET_TEST_RESOURCES: {
        this.invalidInputs = this.testResourceForm.getInvalidInputs();
        return !this.invalidInputs.length;
      }
      default: {
        break;
      }
    }
    return true;
  }
}
