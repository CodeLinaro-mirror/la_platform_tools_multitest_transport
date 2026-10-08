/**
 * Copyright 2025 Google LLC
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

import {Location} from '@angular/common';
import {Component, inject, OnInit, ChangeDetectionStrategy} from '@angular/core';
import {UntypedFormBuilder, UntypedFormGroup} from '@angular/forms';
import {ActivatedRoute} from '@angular/router';
import {zip} from 'rxjs';
import {finalize} from 'rxjs/operators';
import {TestResourceClassType} from '../build_channels/test_resource_form';
import {MttClient} from '../services/mtt_client';
import {
  BuildChannel,
  OptionDef,
  Test,
  TestPlan,
  TestResourceObj,
  TestRunAction,
  TestRunActionRef,
  TestRunConfig,
  TestRunHook,
  testResourceDefToObj,
} from '../services/mtt_models';
import {Notifier} from '../services/notifier';
import {getLocalTimezone, ScheduleType} from '../shared/schedule_time_form';
import {buildApiErrorMessage} from '../shared/util';

interface TestResourceGroup {
  testId: string;
  testName: string;
  resources: TestResourceObj[];
}

/** A page for editing test suites. */
@Component({
  changeDetection: ChangeDetectionStrategy.Eager,standalone: false,
  selector: 'app-edit-test-suites-page',
  templateUrl: './edit_test_suites_page.ng.html',
  styleUrls: ['./edit_test_suites_page.scss']
})
export class EditTestSuitesPage implements OnInit {
  isLoading = false;
  testPlans: TestPlan[] = [];
  tests: {[id: string]: Test} = {};
  actionsFormGroup!: UntypedFormGroup;
  resourcesFormGroup!: UntypedFormGroup;

  allActions: {[id: string]: TestRunAction} = {};
  allHooks: {[name: string]: TestRunHook} = {};
  referencedActions: TestRunAction[] = [];
  /** IDs of referenced actions which no longer exist. */
  unknownActionIds: string[] = [];
  effectiveOptionDefs: {[actionId: string]: OptionDef[]} = {};
  /** Current value hint per action and option name (empty if not set). */
  currentValueHints: {[actionId: string]: {[optionName: string]: string}} =
      {};
  actionRefsMap = new Map<string, TestRunActionRef[]>();

  buildChannels: BuildChannel[] = [];
  testResourceGroups: TestResourceGroup[] = [];
  readonly TestResourceClassType = TestResourceClassType;
  currentLabel = '';

  /** Client-side local timezone, used as the default for new schedules. */
  localTimezone = getLocalTimezone();

  /** Selected schedule type, '' means keep the original schedules. */
  selectedScheduleType: ScheduleType|'' = '';
  /** Cron expression to apply, null means keep the original schedules. */
  batchCronExp: string|null = null;
  /** Time zone to apply to all test plans that get a new schedule. */
  batchTimezone = this.localTimezone;
  /** Original schedule values by test plan ID (undefined if not set). */
  readonly originalCronExps = new Map<string, string|undefined>();
  readonly originalTimezones = new Map<string, string|undefined>();
  /** Distinct timezones used by the loaded test plans. */
  originalTimezoneOptions: string[] = [];

  private readonly route = inject(ActivatedRoute);
  private readonly mttClient = inject(MttClient);
  private readonly notifier = inject(Notifier);
  private readonly formBuilder = inject(UntypedFormBuilder);
  private readonly location = inject(Location);

  ngOnInit() {
    this.actionsFormGroup = this.formBuilder.group({});
    this.resourcesFormGroup = this.formBuilder.group({'resourcesCtrl': ['']});

    zip(
      this.mttClient.getTests(),
      this.mttClient.testRunActions.list(),
      this.mttClient.testRunActions.listTestRunHooks(),
      this.mttClient.getBuildChannels(),
    ).subscribe(
      ([testList, actionList, hookList, buildChannelList]) => {
        if (testList.tests) {
          for (const test of testList.tests) {
            this.tests[test.id!] = test;
          }
        }
        for (const action of actionList) {
          this.allActions[action.id] = action;
        }
        if (hookList.test_run_hooks) {
          for (const hook of hookList.test_run_hooks) {
            this.allHooks[hook.name] = hook;
          }
        }
        if (buildChannelList.build_channels) {
          this.buildChannels = buildChannelList.build_channels;
        }

        this.route.queryParams.subscribe((params) => {
          const label = params['label'];
          if (label) {
            this.currentLabel = label;
            this.loadTestPlans(label);
          }
        });
      },
      (error) => {
        this.notifier.showError(
          'Failed to load page data.',
          buildApiErrorMessage(error),
        );
      },
    );
  }

  loadTestPlans(label: string) {
    this.mttClient.getTestPlans().subscribe(
        (result) => {
          this.testPlans = (result.test_plans || [])
                               .filter(
                                   (tp: TestPlan) => tp.labels &&
                                       tp.labels.includes(label));

          this.originalCronExps.clear();
          this.originalTimezones.clear();

          const timezones = new Set<string>();
          for (const plan of this.testPlans) {
            if (plan.id) {
              this.originalCronExps.set(plan.id, plan.cron_exp);
              this.originalTimezones.set(plan.id, plan.cron_exp_timezone);
            }
            if (plan.cron_exp_timezone) {
              timezones.add(plan.cron_exp_timezone);
            }
          }
          this.originalTimezoneOptions = Array.from(timezones).sort();

          this.selectedScheduleType = '';
          this.batchCronExp = null;
          this.batchTimezone = this.localTimezone;

          this.initActionSettings();
          this.initResourceSettings();
        },
        (error) => {
          this.notifier.showError(
              `Failed to load test plans with label ${label}.`,
              buildApiErrorMessage(error));
        },
    );
  }

  initActionSettings() {
    this.actionRefsMap.clear();
    this.effectiveOptionDefs = {};
    this.currentValueHints = {};
    this.unknownActionIds = [];
    this.actionsFormGroup = this.formBuilder.group({});

    const uniqueActionIds = new Set<string>();

    for (const plan of this.testPlans) {
      for (const sequence of plan.test_run_sequences || []) {
        for (const config of sequence.test_run_configs) {
          for (const ref of config.test_run_action_refs || []) {
            if (!ref.action_id) {
              continue;
            }
            if (!this.actionRefsMap.has(ref.action_id)) {
              this.actionRefsMap.set(ref.action_id, []);
            }
            this.actionRefsMap.get(ref.action_id)!.push(ref);
            uniqueActionIds.add(ref.action_id);
          }
        }
      }
    }

    this.referencedActions = Array.from(uniqueActionIds, id => this.allActions[id])
      .filter(action => !!action);
    this.unknownActionIds =
        Array.from(uniqueActionIds).filter(id => !this.allActions[id]);

    for (const action of this.referencedActions) {
      const refs = this.actionRefsMap.get(action.id) || [];
      const optionDefs = this.getActionOptionDefs(action, refs);
      this.effectiveOptionDefs[action.id] = optionDefs;

      const hints: {[optionName: string]: string} = {};
      for (const def of optionDefs) {
        hints[def.name] = this.getCurrentValueHint(action, refs, def.name);
      }
      this.currentValueHints[action.id] = hints;

      if (optionDefs.length > 0) {
        const fields: {[key: string]: string} = {};
        for (const def of optionDefs) {
          fields[def.name] = '';
        }
        this.actionsFormGroup.addControl(
          action.id,
          this.formBuilder.group(fields)
        );
      }
    }
  }

  /**
   * Returns the configurable options of an action: all options supported by
   * its hook (in definition order), followed by any additional options set on
   * the action or on its references.
   */
  private getActionOptionDefs(
      action: TestRunAction, refs: TestRunActionRef[]): OptionDef[] {
    const optionDefs: OptionDef[] = [];
    const names = new Set<string>();
    const addOptionDef = (def: OptionDef) => {
      if (def.name && !names.has(def.name)) {
        names.add(def.name);
        optionDefs.push(def);
      }
    };
    const toStringOptionDef = (name: string): OptionDef =>
        ({name, value_type: 'STRING', choices: [], default: ''});

    for (const def of this.allHooks[action.hook_class_name]?.option_defs ||
         []) {
      addOptionDef(def);
    }
    for (const option of action.options || []) {
      addOptionDef(toStringOptionDef(option.name));
    }
    for (const ref of refs) {
      for (const option of ref.options || []) {
        addOptionDef(toStringOptionDef(option.name));
      }
    }
    return optionDefs;
  }

  /**
   * Returns a hint describing the current value of an action option across all
   * references. A reference option overrides the action option, which matches
   * how the backend resolves action references.
   */
  private getCurrentValueHint(
      action: TestRunAction, refs: TestRunActionRef[],
      optionName: string): string {
    const actionOption = (action.options || []).find(o => o.name === optionName);
    const values = new Set<string>();
    for (const ref of refs) {
      const refOption = (ref.options || []).find(o => o.name === optionName);
      values.add((refOption ?? actionOption)?.value ?? '');
    }
    if (values.size > 1) {
      return 'Current: varies';
    }
    const [value] = Array.from(values);
    return value ? `Current: ${value}` : '';
  }

  initResourceSettings() {
    const testIds = new Set<string>();
    const sampleConfigByTestId: {[testId: string]: TestRunConfig} = {};

    for (const plan of this.testPlans) {
      for (const sequence of plan.test_run_sequences || []) {
        for (const config of sequence.test_run_configs) {
          if (!testIds.has(config.test_id)) {
            testIds.add(config.test_id);
            sampleConfigByTestId[config.test_id] = config;
          }
        }
      }
    }

    this.testResourceGroups = [];
    for (const testId of Array.from(testIds)) {
      const test = this.tests[testId];
      if (!test) continue;
      const sampleConfig = sampleConfigByTestId[testId];
      this.testResourceGroups.push({
        testId,
        testName: test.name,
        resources: this.combineResources(test, sampleConfig),
      });
    }
  }

  /**
   * Applies the selected batch schedule to all test plans.
   *
   * - Keep Original: original cron expression and time zone.
   * - Manual: no cron expression, original time zone left untouched.
   * - Periodic/Custom: the batch cron expression and time zone (defaults to
   *   the local time zone) are applied to every test plan. If no cron
   *   expression was entered yet, the original schedule is kept.
   */
  updateBatchSchedule() {
    for (const plan of this.testPlans) {
      if (!plan.id) continue;
      const originalCron = this.originalCronExps.get(plan.id);
      const originalTimezone = this.originalTimezones.get(plan.id);

      switch (this.selectedScheduleType) {
        case ScheduleType.MANUAL: {
          plan.cron_exp = '';
          plan.cron_exp_timezone = originalTimezone;
          break;
        }
        case ScheduleType.PERIODIC:
        case ScheduleType.CUSTOM: {
          if (this.batchCronExp) {
            plan.cron_exp = this.batchCronExp;
            plan.cron_exp_timezone = this.batchTimezone;
          } else {
            plan.cron_exp = originalCron;
            plan.cron_exp_timezone = originalTimezone;
          }
          break;
        }
        default: {
          // Keep original
          plan.cron_exp = originalCron;
          plan.cron_exp_timezone = originalTimezone;
          break;
        }
      }
    }
  }

  /** Whether Custom was selected without a cron expression. */
  get showEmptyCronHint(): boolean {
    return this.selectedScheduleType === ScheduleType.CUSTOM &&
        !this.batchCronExp;
  }

  combineResources(
    test: Test,
    sampleConfig: TestRunConfig,
  ): TestResourceObj[] {
    const updatedObjsMap: {[name: string]: TestResourceObj} = {};

    if (test && test.test_resource_defs) {
      for (const def of test.test_resource_defs) {
        updatedObjsMap[def.name] = testResourceDefToObj(def);
      }
    }

    if (sampleConfig.test_resource_objs) {
      for (const oldObj of sampleConfig.test_resource_objs) {
        if (oldObj.name) {
          updatedObjsMap[oldObj.name] = {...oldObj};
        }
      }
    }

    for (const name in updatedObjsMap) {
      if (updatedObjsMap.hasOwnProperty(name)) {
        updatedObjsMap[name].url = '';
      }
    }

    return Object.values(updatedObjsMap);
  }

  /**
   * Applies the entered action option values to all references of each action.
   * Blank inputs keep the current values of each test plan.
   */
  applyActionOptions() {
    for (const actionId of Object.keys(this.actionsFormGroup.controls)) {
      const group = this.getActionGroup(actionId);
      if (!group) {
        continue;
      }
      for (const [optionName, control] of Object.entries(group.controls)) {
        const value = String(control.value ?? '').trim();
        this.updateActionOption(actionId, optionName, value);
      }
    }
  }

  /** Sets an option on all references of an action, ignoring empty values. */
  updateActionOption(actionId: string, optionName: string, value: string) {
    const refs = this.actionRefsMap.get(actionId);
    if (!refs || value === '') {
      return;
    }

    for (const ref of refs) {
      ref.options = ref.options || [];
      const option = ref.options.find((o) => o.name === optionName);
      if (option) {
        option.value = value;
      } else {
        ref.options.push({name: optionName, value});
      }
    }
  }

  back() {
    this.location.back();
  }

  mergeConfigResources(config: TestRunConfig, newResources: TestResourceObj[]) {
    const existingResourcesMap = new Map(
      (config.test_resource_objs || []).map((r) => [r.name, r]),
    );

    for (const res of newResources) {
      const existing = existingResourcesMap.get(res.name!);
      if (existing) {
        if (!res.url) {
          existingResourcesMap.set(res.name!, {...res, url: existing.url});
        } else {
          existingResourcesMap.set(res.name!, {...res});
        }
      }
    }

    config.test_resource_objs = Array.from(existingResourcesMap.values());
  }

  getActionGroup(actionId: string): UntypedFormGroup | null {
    const control = this.actionsFormGroup.controls[actionId];
    return (control as UntypedFormGroup) || null;
  }

  update() {
    if (!this.testPlans || this.testPlans.length === 0) {
      this.back();
      return;
    }

    this.isLoading = true;

    this.applyActionOptions();

    const resourcesByTestId = new Map<string, TestResourceObj[]>();
    for (const group of this.testResourceGroups) {
      resourcesByTestId.set(group.testId, group.resources);
    }

    for (const plan of this.testPlans) {
      for (const sequence of plan.test_run_sequences || []) {
        for (const config of sequence.test_run_configs) {
          const newResources = resourcesByTestId.get(config.test_id);
          if (newResources) {
            this.mergeConfigResources(config, newResources);
          }
        }
      }
    }

    this.mttClient
      .updateTestPlans({test_plans: this.testPlans})
      .pipe(
        finalize(() => {
          this.isLoading = false;
        }),
      )
      .subscribe(
        () => {
          this.notifier.showMessage('Test plans updated successfully.');
          this.back();
        },
        (error) => {
          this.notifier.showError(
            'Failed to update test plans.',
            buildApiErrorMessage(error),
          );
        },
      );
  }
}