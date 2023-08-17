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
import {AfterViewInit, Component, Inject, OnInit, ViewChild} from '@angular/core';
import {MatButton} from '@angular/material/button';
import {MatChipInputEvent} from '@angular/material/chips';
import {MatStepper} from '@angular/material/stepper';
import {Title} from '@angular/platform-browser';
import {ActivatedRoute, Params, Router} from '@angular/router';
import {forkJoin, Observable, of as observableOf} from 'rxjs';
import {catchError, filter, finalize, first, map, switchMap} from 'rxjs/operators';

import {TestResourceForm} from '../build_channels/test_resource_form';
import {APP_DATA, AppData} from '../services/app_data';
import {MttClient} from '../services/mtt_client';
import {DeviceSearchCriteria, LabDeviceInfosResponse} from '../services/mtt_lab_models';
import * as mttModels from '../services/mtt_models';
import {RerunContext, testResourceDefToObj} from '../services/mtt_models';
import {MttObjectMapService, newMttObjectMap} from '../services/mtt_object_map';
import {Notifier} from '../services/notifier';
import {TfcClient} from '../services/tfc_client';
import {FormChangeTracker} from '../shared/can_deactivate';
import {APPLICATION_NAME} from '../shared/shared_module';
import {TestRunConfigForm} from '../shared/test_run_config_form';
import {buildApiErrorMessage, resetStepCompletion} from '../shared/util';

enum Step {
  CONFIGURE_TEST_RUN = 0,
  SELECT_DEVICES = 1,
  ADD_ACTIONS = 2,
  SET_TEST_RESOURCES = 3,
  ADD_RERUN_CONFIGS = 4,
}
const TOTAL_STEPS = 5;
const DISK_SPACE_USAGE_ALARMS = ['disk_space._data.disk_space_usage'];

/**
 * Form for running a new test
 */
@Component({
  selector: 'new-test-run-page',
  styleUrls: ['new_test_run_page.css'],
  templateUrl: './new_test_run_page.ng.html',
})
export class NewTestRunPage extends FormChangeTracker implements OnInit,
                                                                 AfterViewInit {
  @ViewChild('backButton', {static: false}) backButton?: MatButton;
  // Validation variable
  @ViewChild(TestRunConfigForm, {static: true})
  testRunConfigForm!: TestRunConfigForm;
  @ViewChild(TestResourceForm, {static: true})
  testResourceForm!: TestResourceForm;
  errorMessage = '';
  warningMessage = '';

  // Record each step whether it has finished or not
  stepCompletionStatusMap: {[stepNum: number]: boolean} = {};
  step = Step;
  resetStepCompletion = resetStepCompletion;
  totalSteps = TOTAL_STEPS;

  prevTestRunId?: string;
  rerunContext?: RerunContext;

  mttObjectMap = newMttObjectMap();

  testRunConfig = mttModels.initTestRunConfig();
  rerunConfigs: mttModels.TestRunConfig[] = [];
  selectedDeviceActions: mttModels.DeviceAction[] = [];
  selectedTestRunActions: mttModels.TestRunAction[] = [];

  labels: string[] = [];
  nodeConfigTestResourceUrls: mttModels.NameValuePair[] = [];

  isLoading = false;
  isStartingTestRun = false;

  /** Keys used to separate labels */
  readonly separatorKeyCodes: number[] = [ENTER, COMMA];

  back() {
    this.router.navigate(['tests']);
  }

  constructor(
      private readonly liveAnnouncer: LiveAnnouncer,
      private readonly router: Router,
      private readonly route: ActivatedRoute,
      private readonly mttClient: MttClient,
      private readonly mttObjectMapService: MttObjectMapService,
      private readonly notifier: Notifier,
      private readonly title: Title,
      private readonly tfcClient: TfcClient,
      @Inject(APP_DATA) readonly appData: AppData,
  ) {
    super();
  }

  ngOnInit() {
    this.title.setTitle(`${APPLICATION_NAME} - New Test Run`);

    this.route.queryParams.pipe(first()).subscribe((params: Params) => {
      this.prevTestRunId = params['prevTestRunId'];
      this.testRunConfig.test_id = params['testId'];
      this.loadData(this.testRunConfig.test_id, this.prevTestRunId);
    });

    // Initialize step completion status map
    resetStepCompletion(0, this.stepCompletionStatusMap, this.totalSteps);
  }

  ngAfterViewInit() {
    this.backButton!.focus();
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
      case Step.CONFIGURE_TEST_RUN: {
        this.invalidInputs = this.testRunConfigForm.getInvalidInputs();
        return !this.invalidInputs.length;
      }
      case Step.SELECT_DEVICES: {
        const res = !!this.testRunConfig.device_specs &&
            0 < this.testRunConfig.device_specs.length;
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
   * Load MTT models data
   * @param testId ID of the selected test to run
   * @param prevTestRunId ID of a previous test run to rerun
   */
  loadData(testId?: string, prevTestRunId?: string) {
    // Make API calls
    const mttObjectMapObs =
        this.mttObjectMapService.getMttObjectMap(true /* forceUpdate */);
    const nodeConfigObs = this.mttClient.getNodeConfig();
    const prevTestRunObs = prevTestRunId ?
        this.mttClient.getTestRun(prevTestRunId) :
        observableOf(null);

    this.isLoading = true;
    this.liveAnnouncer.announce('Loading', 'polite');

    // Get API call results
    forkJoin([mttObjectMapObs, nodeConfigObs, prevTestRunObs])
        .pipe(first())
        .subscribe(
            ([mttObjectMapRes, nodeConfigRes, prevTestRunRes]) => {
              this.mttObjectMap = mttObjectMapRes;

              // Node Configs
              this.nodeConfigTestResourceUrls =
                  nodeConfigRes.test_resource_default_download_urls || [];

              // Load config values from either previous test run or test
              // suite config defaults
              if (prevTestRunRes) {
                this.loadPrevTestRun(prevTestRunRes);
              } else {
                this.testRunConfig = mttModels.initTestRunConfig(
                    testId ? this.mttObjectMap.testMap[testId] :
                             Object.values(this.mttObjectMap.testMap)[0]);
              }

              this.updateTestResources();

              this.isLoading = false;
              this.liveAnnouncer.announce('Test run loaded', 'assertive');
            },
            error => {
              this.notifier.showError(
                  'Failed to load test run.', buildApiErrorMessage(error));
            });
  }

  /** Load config values from a previous test run */
  loadPrevTestRun(prevTestRun: mttModels.TestRun|null) {
    if (!prevTestRun) {
      return;
    }

    if (prevTestRun.test) {
      this.testRunConfig.test_id = prevTestRun.test.id;
    }

    if (prevTestRun.test_run_config) {
      /**
       * TODO: If the run target is something other than serials,
       * the run target will be cleared.
       */
      this.testRunConfig = prevTestRun.test_run_config;
      this.testRunConfig.device_specs = this.testRunConfig.device_specs || [];

      // Load device actions
      const deviceActionIds = this.testRunConfig.before_device_action_ids || [];
      this.selectedDeviceActions = deviceActionIds.map(
          id => this.mttObjectMap.deviceActionMap[id] || {});

      // Load test run actions
      const testRunActionRefs = this.testRunConfig.test_run_action_refs || [];
      this.selectedTestRunActions = testRunActionRefs.map(ref => {
        const action = this.mttObjectMap.testRunActionMap[ref.action_id] || {};
        action.options = ref.options;
        return action;
      });
    }

    if (prevTestRun.test_resources) {
      this.testRunConfig.test_resource_objs = prevTestRun.test_resources;
    }

    this.labels = prevTestRun.labels || [];
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
    this.testRunConfig.before_device_action_ids =
        this.selectedDeviceActions.map(action => action.id);
    this.updateTestResources();
  }

  /**
   * Converts the selected test run actions to ids and stores it in the config
   */
  updateConfigTestRunActionIds() {
    this.testRunConfig.test_run_action_refs =
        this.selectedTestRunActions.map(action => {
          return {action_id: action.id, options: action.options};
        });
  }

  /**
   * Under set test resource types, we need to update the required
   * test resources on data changes
   */
  updateTestResources() {
    const updatedObjsMap: {[name: string]: mttModels.TestResourceObj;} = {};

    // Get resource defs from Test
    if (typeof this.testRunConfig.test_id !== 'undefined') {
      const test = this.mttObjectMap.testMap[this.testRunConfig.test_id];
      if (test && test.test_resource_defs) {
        for (const def of test.test_resource_defs) {
          updatedObjsMap[def.name] = testResourceDefToObj(def);
        }
      }
    }

    // Get resource defs from Device Actions
    for (const deviceAction of this.selectedDeviceActions) {
      if (deviceAction.test_resource_defs) {
        for (const def of deviceAction.test_resource_defs) {
          updatedObjsMap[def.name] = testResourceDefToObj(def);
        }
      }
    }

    // Overwrite urls with node config default download values
    for (const nodeUrl of this.nodeConfigTestResourceUrls) {
      if (nodeUrl.name in updatedObjsMap) {
        updatedObjsMap[nodeUrl.name].url = nodeUrl.value || '';
      }
    }

    // Overwrite urls with previously entered values
    if (this.testRunConfig.test_resource_objs) {
      for (const oldObj of this.testRunConfig.test_resource_objs) {
        if (oldObj.name && oldObj.name in updatedObjsMap) {
          updatedObjsMap[oldObj.name] = oldObj;
        }
      }
    }

    // Save updated values
    this.testRunConfig.test_resource_objs = Object.values(updatedObjsMap);
  }

  addLabel(event: MatChipInputEvent) {
    const input = event.chipInput.inputElement;
    const value = event.value;

    if ((value || '').trim() && this.labels.indexOf(value.trim()) === -1) {
      this.labels.push(value.trim());
    }

    if (input) {
      input.value = '';
    }
  }

  removeLabel(label: string) {
    const index = this.labels.indexOf(label);
    if (index >= 0) {
      this.labels.splice(index, 1);
    }
  }

  startTestRun(ignoreWarnings = false) {
    // TODO: Add input verification and error message
    if (!this.validateStep(Step.SET_TEST_RESOURCES)) {
      return;
    }

    this.isStartingTestRun = true;
    this.checkDiskSpace(ignoreWarnings)
        .pipe(
            filter(result => result), switchMap(() => {
              const newTestRunRequest: mttModels.NewTestRunRequest = {
                labels: this.labels,
                test_run_config: {...this.testRunConfig} as
                    mttModels.TestRunConfig,
                rerun_context: this.rerunContext || {},
                rerun_configs: this.rerunConfigs,
              };
              return this.mttClient.createNewTestRunRequest(newTestRunRequest)
                  .pipe(first());
            }),
            finalize(() => {
              this.isStartingTestRun = false;
            }))
        .subscribe(
            result => {
              super.resetForm();
              this.router.navigate([`test_runs/${result.id}`]);
              this.notifier.showMessage(`Test run '${result.id}' started`);
            },
            error => {
              this.notifier.showError(
                  'Failed to schedule a new test run.',
                  buildApiErrorMessage(error));
            });
  }

  checkDiskSpace(skip = false): Observable<boolean> {
    if (skip) {
      return observableOf(true);
    }

    const deviceSpecs =
        (this.testRunConfig.device_specs || [])
            .concat(this.rerunConfigs.map(config => config.device_specs || [])
                        .flat());
    const deviceSerial = this.getDeviceSerials(deviceSpecs);

    let deviceInfoObservable: Observable<LabDeviceInfosResponse>;
    if (deviceSerial.length === 0) {
      deviceInfoObservable =
          observableOf({more: false} as LabDeviceInfosResponse);
    } else {
      const query: DeviceSearchCriteria = {
        deviceSerial,
        includeOfflineDevices: false,
      };
      deviceInfoObservable =
          this.tfcClient.queryDeviceInfos(query, deviceSerial.length);
    }


    return deviceInfoObservable.pipe(
        map(response => {
          const hostnames = new Set<string>();
          // Hostname of controller
          if (this.appData.hostname) {
            hostnames.add(this.appData.hostname);
          }
          // Hostnames of selected devices
          for (const deviceInfo of response.deviceInfos || []) {
            if (deviceInfo.hostname) {
              hostnames.add(deviceInfo.hostname);
            }
          }
          return Array.from(hostnames);
        }),
        switchMap(hostnames => {
          if (hostnames.length === 0) {
            return observableOf([]);
          }
          return forkJoin(hostnames.map(
              hostname =>
                  this.mttClient.netdata
                      .getAlarms(DISK_SPACE_USAGE_ALARMS, hostname)
                      .pipe(catchError(
                          () => observableOf(
                              {alarms: []} as mttModels.NetdataAlarmList)))));
        }),
        map(alarmLists => {
          const alarms =
              alarmLists.map(alarmList => alarmList.alarms || []).flat();
          if (alarms.length === 0) {
            return true;
          }

          this.warningMessage = `Low disk space warning on ${
              alarms[0].hostname} (${alarms[0].value} used)`;
          if (alarms.length > 1) {
            this.warningMessage += ` and ${alarms.length - 1} other host(s)`;
          }
          return false;
        }));
  }

  private getDeviceSerials(deviceSpecs: string[]): string[] {
    const deviceSerials = new Set<string>();
    for (const spec of deviceSpecs) {
      const match = /^device_serial:(\S+)$/.exec(spec);
      if (match) {
        deviceSerials.add(match[1]);
      }
    }
    return Array.from(deviceSerials);
  }
}
