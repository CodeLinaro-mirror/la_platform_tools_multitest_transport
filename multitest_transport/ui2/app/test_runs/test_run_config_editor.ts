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

import {Component, EventEmitter, Inject, OnInit, Output, ViewChild} from '@angular/core';
import {MAT_DIALOG_DATA, MatDialogRef} from '@angular/material/dialog';
import {MatStepper} from '@angular/material/stepper';

import {TestResourceClassType, TestResourceForm} from '../build_channels/test_resource_form';
import * as mttModels from '../services/mtt_models';
import {MttObjectMapService, newMttObjectMap} from '../services/mtt_object_map';
import {FormChangeTracker} from '../shared/can_deactivate';
import {TestRunConfigForm} from '../shared/test_run_config_form';
import {resetStepCompletion} from '../shared/util';

/**
 * Data format when passed to TestRunConfigEditor
 * @param editMode determine whether the editor is editing existed config or
 *     creating a new config.
 * @param testRunConfig target config to edit.
 */
export interface TestRunConfigEditorData {
  editMode: boolean;
  testRunConfig: Partial<mttModels.TestRunConfig>;
}

enum Step {
  CONFIGURATION = 0,
  SELECT_RUN_TARGETS = 1,
  ADD_DEVICE_ACTIONS = 2,
  SET_TEST_RESOURCES = 3,
}
const TOTAL_STEPS = 4;

/**
 * This component is used to create or update a test run config.
 */
@Component({
  selector: 'test-run-config-editor',
  styleUrls: ['test_run_config_editor.css'],
  templateUrl: './test_run_config_editor.ng.html',
  providers: [{provide: FormChangeTracker, useExisting: TestRunConfigEditor}]
})
export class TestRunConfigEditor extends FormChangeTracker implements OnInit {
  @ViewChild(TestResourceForm, {static: true})
  testResourceForm!: TestResourceForm;
  @Output()
  readonly configSubmitted = new EventEmitter<mttModels.TestRunConfig>();

  // Record each step whether it has finished or not
  stepCompletionStatusMap: {[stepNum: number]: boolean} = {};
  step = Step;
  resetStepCompletion = resetStepCompletion;
  totalSteps = TOTAL_STEPS;

  // Validation variable
  @ViewChild(TestRunConfigForm, {static: true})
  testRunConfigForm!: TestRunConfigForm;
  errorMessage = '';

  readonly TestResourceClassType = TestResourceClassType;

  isLoading = false;
  mttObjectMap = newMttObjectMap();
  selectedDeviceActions: mttModels.DeviceAction[] = [];
  selectedTestRunActions: mttModels.TestRunAction[] = [];

  constructor(
      private readonly dialogRef: MatDialogRef<TestRunConfigEditor>,
      readonly mttObjectMapService: MttObjectMapService,
      @Inject(MAT_DIALOG_DATA) public data: TestRunConfigEditorData) {
    super();
    // When user clicked outside of the dialog, close the dialog
    dialogRef.backdropClick().subscribe(() => {
      this.dialogRef.close();
    });
  }

  ngOnInit() {
    // Initialize step completion status map
    this.resetStepCompletion(0, this.stepCompletionStatusMap, this.totalSteps);
    this.load();
  }

  load() {
    this.mttObjectMapService.getMttObjectMap().subscribe((res) => {
      this.mttObjectMap = res;
      this.loadSelectedActions();
    });
  }

  loadSelectedActions() {
    const deviceActionIds =
        this.data.testRunConfig.before_device_action_ids || [];
    this.selectedDeviceActions =
        deviceActionIds.map(id => this.mttObjectMap.deviceActionMap[id] || {});

    // Load test run actions
    const testRunActionRefs =
        this.data.testRunConfig.test_run_action_refs || [];
    this.selectedTestRunActions = testRunActionRefs.map(ref => {
      const action = this.mttObjectMap.testRunActionMap[ref.action_id] || {};
      action.options = ref.options;
      return action;
    });
    this.updateTestResources();
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
      case Step.CONFIGURATION: {
        this.invalidInputs = this.testRunConfigForm.getInvalidInputs();
        return !this.invalidInputs.length;
      }
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

  /**
   * Update the device actions and the test resources according to the selected
   * run targets
   */
  updateSelectedDeviceActions(deviceSpecs: string[]) {
    this.selectedDeviceActions = mttModels.updateSelectedDeviceActions(
        this.selectedDeviceActions,
        Object.values(this.mttObjectMap.deviceActionMap), deviceSpecs);
    this.updateConfigDeviceActionIds();
  }

  /**
   * Converts the selected device actions to ids and stores it in the config
   */
  updateConfigDeviceActionIds() {
    this.data.testRunConfig.before_device_action_ids =
        this.selectedDeviceActions.map(action => action.id);
    this.updateTestResources();
  }

  /**
   * Converts the selected test run actions to ids and stores it in the config
   */
  updateConfigTestRunActionIds() {
    this.data.testRunConfig.test_run_action_refs =
        this.selectedTestRunActions.map(action => {
          return {action_id: action.id, options: action.options};
        });
  }

  /**
   * Update the required test resources on data changes
   */
  updateTestResources() {
    const updatedObjsMap: {[name: string]: mttModels.TestResourceObj;} = {};

    // Get resource defs from Test
    if (typeof this.data.testRunConfig.test_id !== 'undefined') {
      const test = this.mttObjectMap.testMap[this.data.testRunConfig.test_id];
      if (test && test.test_resource_defs) {
        for (const def of test.test_resource_defs) {
          updatedObjsMap[def.name] = mttModels.testResourceDefToObj(def);
        }
      }
    }

    // Get resource defs from Device Actions
    for (const deviceAction of this.selectedDeviceActions) {
      if (deviceAction.test_resource_defs) {
        for (const def of deviceAction.test_resource_defs) {
          updatedObjsMap[def.name] = mttModels.testResourceDefToObj(def);
        }
      }
    }

    // Overwrite urls with previously entered values
    if (this.data.testRunConfig.test_resource_objs) {
      for (const oldObj of this.data.testRunConfig.test_resource_objs) {
        if (oldObj.name && oldObj.name in updatedObjsMap) {
          updatedObjsMap[oldObj.name] = oldObj;
        }
      }
    }

    // Save updated values
    this.data.testRunConfig.test_resource_objs = Object.values(updatedObjsMap);
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
}
