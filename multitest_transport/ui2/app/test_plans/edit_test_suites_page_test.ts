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

// tslint:disable:enforce-name-casing

import {Location} from '@angular/common';
import {ComponentFixture, TestBed} from '@angular/core/testing';
import {UntypedFormControl} from '@angular/forms';
import {By} from '@angular/platform-browser';
import {NoopAnimationsModule} from '@angular/platform-browser/animations';
import {ActivatedRoute} from '@angular/router';
import {Observable, of as observableOf} from 'rxjs';

import {MttClient} from '../services/mtt_client';
import {NameValuePair, Test, TestPlan, TestResourceObj, TestResourceType, TestRunAction, TestRunActionRef, TestRunConfig, TestRunHook} from '../services/mtt_models';
import {Notifier} from '../services/notifier';
import {PeriodicType, ScheduleTimeForm, ScheduleType} from '../shared/schedule_time_form';

import {EditTestSuitesPage} from './edit_test_suites_page';
import {TestPlansModule} from './test_plans_module';

describe('EditTestSuitesPage', () => {
  let component: EditTestSuitesPage;
  let fixture: ComponentFixture<EditTestSuitesPage>;
  let mttClient: jasmine.SpyObj<MttClient>;
  let notifier: jasmine.SpyObj<Notifier>;
  let location: jasmine.SpyObj<Location>;

  beforeEach(async () => {
    const mttClientSpy = jasmine.createSpyObj('MttClient', [
      'getTests', 'getBuildChannels', 'getTestPlans', 'updateTestPlan',
      'updateTestPlans'
    ]);
    const testRunActionsSpy =
        jasmine.createSpyObj('TestRunActions', ['list', 'listTestRunHooks']);

    mttClient = {...mttClientSpy, testRunActions: testRunActionsSpy} as
        unknown as jasmine.SpyObj<MttClient>;

    // Mock return values for observables
    mttClient.getTests.and.returnValue(observableOf({tests: []}));
    (mttClient.testRunActions.list as jasmine.Spy)
        .and.returnValue(observableOf([]));
    (mttClient.testRunActions.listTestRunHooks as jasmine.Spy)
        .and.returnValue(observableOf({test_run_hooks: []}));
    mttClient.getBuildChannels.and.returnValue(
        observableOf({build_channels: []}));
    mttClient.getTestPlans.and.returnValue(observableOf({test_plans: []}));

    notifier = jasmine.createSpyObj('Notifier', ['showError', 'showMessage']);
    location = jasmine.createSpyObj('Location', ['back']);

    await TestBed
        .configureTestingModule({
          imports: [
            NoopAnimationsModule,
            TestPlansModule,
          ],
          providers: [
            {provide: MttClient, useValue: mttClient},
            {provide: Notifier, useValue: notifier},
            {provide: Location, useValue: location},
            {
              provide: ActivatedRoute,
              useValue:
                  {queryParams: observableOf({}), snapshot: {queryParams: {}}}
            },
          ]
        })
        .compileComponents();
  });

  beforeEach(() => {
    fixture = TestBed.createComponent(EditTestSuitesPage);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('updateActionOption should update existing option value', () => {
    const actionId = 'action1';
    const optionName = 'option1';
    const ref = {
      action_id: actionId,
      options: [{name: optionName, value: 'oldValue'}],
    };
    component.actionRefsMap.set(actionId, [ref]);

    component.updateActionOption(actionId, optionName, 'newValue');

    expect(ref.options[0].value).toBe('newValue');
  });

  it('updateActionOption should add new option if not exists', () => {
    const actionId = 'action1';
    const optionName = 'option1';
    const ref = {action_id: actionId, options: [] as NameValuePair[]};
    component.actionRefsMap.set(actionId, [ref]);

    component.updateActionOption(actionId, optionName, 'newValue');

    expect(ref.options.length).toBe(1);
    expect(ref.options[0]).toEqual({name: optionName, value: 'newValue'});
  });

  it('update should call updateTestPlans and show success message', () => {
    component.testPlans = [{id: '1', name: 'plan1'} as unknown as TestPlan];
    (mttClient.updateTestPlans as jasmine.Spy).and.callFake(() => {
      expect(component.isLoading).toBe(true);
      return observableOf({});
    });

    component.update();

    expect(mttClient.updateTestPlans).toHaveBeenCalledWith({
      test_plans: component.testPlans,
    });
    expect(notifier.showMessage)
        .toHaveBeenCalledWith(
            'Test plans updated successfully.',
        );
    expect(location.back).toHaveBeenCalled();
    expect(component.isLoading).toBe(false);
  });

  it('update should preserve existing URL if new URL is empty', () => {
    const testId = 'test1';
    const config = {
      test_id: testId,
      test_resource_objs: [{name: 'res1', url: 'http://original'}]
    };
    component.testPlans =
        [{id: '1', test_run_sequences: [{test_run_configs: [config]}]} as
         unknown as TestPlan];

    component.testResourceGroups =
        [{testId, testName: 'Test 1', resources: [{name: 'res1', url: ''}]}];

    (mttClient.updateTestPlans as jasmine.Spy)
        .and.returnValue(observableOf({}));

    component.update();

    expect(config.test_resource_objs[0].url).toBe('http://original');
    expect(mttClient.updateTestPlans).toHaveBeenCalled();
  });

  it('update should update URL if new URL is provided', () => {
    const testId = 'test1';
    const config = {
      test_id: testId,
      test_resource_objs: [{name: 'res1', url: 'http://original'}]
    };
    component.testPlans =
        [{id: '1', test_run_sequences: [{test_run_configs: [config]}]} as
         unknown as TestPlan];

    component.testResourceGroups = [{
      testId,
      testName: 'Test 1',
      resources: [{name: 'res1', url: 'http://new'}]
    }];

    (mttClient.updateTestPlans as jasmine.Spy)
        .and.returnValue(observableOf({}));

    component.update();

    expect(config.test_resource_objs[0].url).toBe('http://new');
    expect(mttClient.updateTestPlans).toHaveBeenCalled();
  });

  it('update should handle error', () => {
    component.testPlans = [{id: '1', name: 'plan1'} as unknown as TestPlan];
    (mttClient.updateTestPlans as jasmine.Spy)
        .and.returnValue(
            new Observable((observer) => {
              observer.error('error');
            }),
        );

    component.update();

    expect(mttClient.updateTestPlans).toHaveBeenCalled();
    expect(notifier.showError).toHaveBeenCalled();
  });

  it('initActionSettings should reset variables', () => {
    component.actionRefsMap.set('id', []);
    component.referencedActions = [{id: '1'} as unknown as TestRunAction];
    component.effectiveOptionDefs = {'1': []};
    component.currentValueHints = {'1': {}};
    component.unknownActionIds = ['2'];
    component.actionsFormGroup.addControl('1', new UntypedFormControl());

    component.initActionSettings();

    expect(component.actionRefsMap.size).toBe(0);
    expect(component.referencedActions).toEqual([]);
    expect(component.unknownActionIds).toEqual([]);
    expect(component.effectiveOptionDefs).toEqual({});
    expect(component.currentValueHints).toEqual({});
    expect(Object.keys(component.actionsFormGroup.controls).length).toBe(0);
  });

  it('initActionSettings should populate referencedActions', () => {
    const actionId = 'action1';
    const action = {id: actionId, options: [{name: 'opt1'}]};
    component.allActions = {[actionId]: action as unknown as TestRunAction};
    component.testPlans = [
      {
        test_run_sequences: [
          {
            test_run_configs: [{test_run_action_refs: [{action_id: actionId}]}],
          },
        ],
      } as unknown as TestPlan,
    ];

    component.initActionSettings();

    expect(component.referencedActions.length).toBe(1);
    expect(component.referencedActions[0])
        .toBe(action as unknown as TestRunAction);
    expect(component.actionRefsMap.get(actionId)!.length).toBe(1);
    expect(component.effectiveOptionDefs[actionId].length).toBe(1);
    expect(component.actionsFormGroup.contains(actionId)).toBe(true);
  });

  describe('test run actions', () => {
    const HOOK: TestRunHook = {
      name: 'HookA',
      option_defs: [
        {name: 'opt_a', value_type: 'STRING'},
        {name: 'opt_b', value_type: 'STRING'},
      ],
    };

    /** Creates a test plan with a single config referencing actions. */
    function newTestPlan(id: string, refs: TestRunActionRef[]): TestPlan {
      return {
        id,
        name: `plan${id}`,
        labels: ['label'],
        test_run_sequences: [{
          test_run_configs: [{test_id: 'test1', test_run_action_refs: refs}],
        }],
      } as unknown as TestPlan;
    }

    function getOptionNames(actionId: string): string[] {
      return component.effectiveOptionDefs[actionId].map(def => def.name);
    }

    function getPageText(): string {
      return (fixture.nativeElement as HTMLElement).textContent || '';
    }

    beforeEach(() => {
      component.allHooks = {[HOOK.name]: HOOK};
    });

    it('lists an action without options with all hook option defs', () => {
      component.allActions = {
        'act1': {id: 'act1', name: 'Action 1', hook_class_name: 'HookA'},
      };
      component.testPlans = [newTestPlan('1', [{action_id: 'act1'}])];

      component.initActionSettings();
      fixture.detectChanges();

      expect(component.referencedActions.map(a => a.id)).toEqual(['act1']);
      expect(getOptionNames('act1')).toEqual(['opt_a', 'opt_b']);
      const group = component.getActionGroup('act1')!;
      expect(group).toBeTruthy();
      expect(Object.keys(group.controls)).toEqual(['opt_a', 'opt_b']);
      expect(group.value).toEqual({'opt_a': '', 'opt_b': ''});
      expect(getPageText()).toContain('Action 1');
    });

    it('lists an action without any configurable parameters', () => {
      component.allActions = {
        'act1': {id: 'act1', name: 'No Params Action', hook_class_name: 'None'},
      };
      component.testPlans = [newTestPlan('1', [{action_id: 'act1'}])];

      component.initActionSettings();
      fixture.detectChanges();

      expect(component.referencedActions.map(a => a.id)).toEqual(['act1']);
      expect(getOptionNames('act1')).toEqual([]);
      expect(component.getActionGroup('act1')).toBeNull();
      expect(getPageText()).toContain('No Params Action');
      expect(getPageText()).toContain('No configurable parameters.');
    });

    it('includes extra option names from the action and its refs', () => {
      component.allActions = {
        'act1': {
          id: 'act1',
          name: 'Action 1',
          hook_class_name: 'HookA',
          options: [
            {name: 'opt_b', value: 'x'},
            {name: 'action_only', value: 'y'},
          ],
        },
      };
      component.testPlans = [
        newTestPlan('1', [{
          action_id: 'act1',
          options: [{name: 'ref_only', value: 'z'}, {name: 'opt_a', value: '1'}],
        }]),
        newTestPlan('2', [{
          action_id: 'act1',
          options: [{name: 'ref_only', value: 'z'}],
        }]),
      ];

      component.initActionSettings();

      expect(getOptionNames('act1')).toEqual([
        'opt_a', 'opt_b', 'action_only', 'ref_only'
      ]);
      expect(Object.keys(component.getActionGroup('act1')!.controls))
          .toEqual(['opt_a', 'opt_b', 'action_only', 'ref_only']);
    });

    it('shows the current value hints', () => {
      component.allActions = {
        'act1': {
          id: 'act1',
          name: 'Action 1',
          hook_class_name: 'HookA',
          options: [{name: 'opt_a', value: 'common'}],
        },
      };
      component.testPlans = [
        // opt_a inherited from the action, opt_b overridden
        newTestPlan('1', [{
          action_id: 'act1',
          options: [{name: 'opt_b', value: 'value1'}],
        }]),
        // opt_a overridden with the same value, opt_b overridden differently
        newTestPlan('2', [{
          action_id: 'act1',
          options: [
            {name: 'opt_a', value: 'common'},
            {name: 'opt_b', value: 'value2'},
          ],
        }]),
      ];

      component.initActionSettings();
      fixture.detectChanges();

      expect(component.currentValueHints['act1']).toEqual({
        'opt_a': 'Current: common',
        'opt_b': 'Current: varies',
      });
      expect(getPageText()).toContain('Current: common');
      expect(getPageText()).toContain('Current: varies');
    });

    it('shows no hint when the option is not set anywhere', () => {
      component.allActions = {
        'act1': {id: 'act1', name: 'Action 1', hook_class_name: 'HookA'},
      };
      component.testPlans = [
        newTestPlan('1', [{action_id: 'act1'}]),
        newTestPlan('2', [{action_id: 'act1', options: []}]),
      ];

      component.initActionSettings();

      expect(component.currentValueHints['act1']).toEqual({
        'opt_a': '',
        'opt_b': '',
      });
    });

    it('shows varies when only some plans override the action value', () => {
      component.allActions = {
        'act1': {
          id: 'act1',
          name: 'Action 1',
          hook_class_name: 'HookA',
          options: [{name: 'opt_a', value: 'default'}],
        },
      };
      component.testPlans = [
        newTestPlan('1', [{action_id: 'act1'}]),
        newTestPlan(
            '2',
            [{action_id: 'act1', options: [{name: 'opt_a', value: 'other'}]}]),
      ];

      component.initActionSettings();

      expect(component.currentValueHints['act1']['opt_a'])
          .toBe('Current: varies');
    });

    /** Sets up two plans referencing act1, returns their refs. */
    function setUpActionRefs(): [TestRunActionRef, TestRunActionRef] {
      component.allActions = {
        'act1': {id: 'act1', name: 'Action 1', hook_class_name: 'HookA'},
      };
      const ref1: TestRunActionRef = {action_id: 'act1'};
      const ref2: TestRunActionRef = {
        action_id: 'act1',
        options: [{name: 'opt_a', value: 'old'}, {name: 'opt_b', value: 'b'}],
      };
      component.testPlans =
          [newTestPlan('1', [ref1]), newTestPlan('2', [ref2])];
      component.initActionSettings();
      (mttClient.updateTestPlans as jasmine.Spy)
          .and.returnValue(observableOf({}));
      return [ref1, ref2];
    }

    /** Simulates typing into an action option input. */
    function typeOption(optionIndex: number, value: string) {
      const el = fixture.nativeElement as HTMLElement;
      const inputs = el.querySelectorAll<HTMLInputElement>('form input');
      inputs[optionIndex].value = value;
      inputs[optionIndex].dispatchEvent(new Event('input'));
      inputs[optionIndex].dispatchEvent(new Event('change'));
    }

    it('does not write typed values before update', () => {
      const [ref1, ref2] = setUpActionRefs();
      fixture.detectChanges();

      typeOption(0, 'new');

      expect(component.getActionGroup('act1')!.value['opt_a']).toBe('new');
      expect(ref1).toEqual({action_id: 'act1'});
      expect(ref2.options).toEqual([
        {name: 'opt_a', value: 'old'},
        {name: 'opt_b', value: 'b'},
      ]);
    });

    it('does not modify refs when a typed value is cleared', () => {
      const [ref1, ref2] = setUpActionRefs();
      fixture.detectChanges();

      typeOption(0, 'new');
      typeOption(0, '');
      component.getActionGroup('act1')!.get('opt_b')!.setValue('   ');
      component.update();

      expect(mttClient.updateTestPlans).toHaveBeenCalled();
      expect(ref1).toEqual({action_id: 'act1'});
      expect(ref2.options).toEqual([
        {name: 'opt_a', value: 'old'},
        {name: 'opt_b', value: 'b'},
      ]);
    });

    it('writes typed values to all refs on update', () => {
      const [ref1, ref2] = setUpActionRefs();
      component.getActionGroup('act1')!.get('opt_a')!.setValue('new');

      component.update();

      expect(mttClient.updateTestPlans).toHaveBeenCalled();
      expect(ref1.options).toEqual([{name: 'opt_a', value: 'new'}]);
      expect(ref2.options).toEqual([
        {name: 'opt_a', value: 'new'},
        {name: 'opt_b', value: 'b'},
      ]);
    });

    it('only writes typed values to the refs of the edited action', () => {
      component.allActions = {
        'act1': {id: 'act1', name: 'Action 1', hook_class_name: 'HookA'},
        'act2': {id: 'act2', name: 'Action 2', hook_class_name: 'HookA'},
      };
      const act1Ref: TestRunActionRef = {action_id: 'act1'};
      const act2Ref: TestRunActionRef = {
        action_id: 'act2',
        options: [{name: 'opt_a', value: 'act2_value'}],
      };
      component.testPlans = [
        newTestPlan('1', [act1Ref, act2Ref]),
      ];
      component.initActionSettings();
      (mttClient.updateTestPlans as jasmine.Spy)
          .and.returnValue(observableOf({}));
      fixture.detectChanges();

      typeOption(0, 'act1_value');  // act1's opt_a
      component.update();

      expect(act1Ref.options).toEqual([{name: 'opt_a', value: 'act1_value'}]);
      expect(act2Ref.options).toEqual([{name: 'opt_a', value: 'act2_value'}]);
    });

    it('supports actions whose hook is unknown', () => {
      component.allActions = {
        'act1': {
          id: 'act1',
          name: 'Action 1',
          hook_class_name: 'MissingHook',
          options: [{name: 'action_opt', value: '1'}],
        },
      };
      component.testPlans = [newTestPlan('1', [{
                               action_id: 'act1',
                               options: [{name: 'ref_opt', value: '2'}],
                             }])];

      component.initActionSettings();

      expect(getOptionNames('act1')).toEqual(['action_opt', 'ref_opt']);
      expect(component.currentValueHints['act1']).toEqual({
        'action_opt': 'Current: 1',
        'ref_opt': 'Current: 2',
      });
    });

    it('lists actions which no longer exist without inputs', () => {
      component.allActions = {};
      const ref: TestRunActionRef = {
        action_id: 'gone',
        options: [{name: 'opt_a', value: 'old'}],
      };
      component.testPlans = [newTestPlan('1', [ref])];
      (mttClient.updateTestPlans as jasmine.Spy)
          .and.returnValue(observableOf({}));

      component.initActionSettings();
      fixture.detectChanges();

      expect(component.referencedActions).toEqual([]);
      expect(component.unknownActionIds).toEqual(['gone']);
      expect(component.getActionGroup('gone')).toBeNull();
      expect(getPageText()).toContain('Unknown action (gone)');
      expect(getPageText())
          .toContain('Action no longer exists; its parameters can\'t be edited.');
      const el = fixture.nativeElement as HTMLElement;
      expect(el.querySelectorAll('form input').length).toBe(0);

      component.update();
      expect(ref.options).toEqual([{name: 'opt_a', value: 'old'}]);
    });
  });

  it('initResourceSettings should populate testResourceGroups and clear URLs',
     () => {
       const testId = 'test1';
       component.testPlans = [
         {
           test_run_sequences: [
             {
               test_run_configs: [{
                 test_id: testId,
                 test_resource_objs: [{name: 'res1', url: 'http://existing'}]
               }],
             },
           ],
         } as unknown as TestPlan,
       ];
       component.tests = {
         [testId]: {name: 'Test 1', test_resource_defs: []} as unknown as Test,
       };

       component.initResourceSettings();

       expect(component.testResourceGroups.length).toBe(1);
       expect(component.testResourceGroups[0].testId).toBe(testId);
       expect(component.testResourceGroups[0].testName).toBe('Test 1');
       expect(component.testResourceGroups[0].resources.length).toBe(1);
       expect(component.testResourceGroups[0].resources[0].name).toBe('res1');
       expect(component.testResourceGroups[0].resources[0].url).toBe('');
     });

  it('initResourceSettings should skip if test not found', () => {
    const testId = 'test1';
    component.testPlans = [
      {
        test_run_sequences: [
          {
            test_run_configs: [{test_id: testId}],
          },
        ],
      } as unknown as TestPlan,
    ];
    component.tests = {};

    component.initResourceSettings();

    expect(component.testResourceGroups.length).toBe(0);
  });

  it('initResourceSettings should clear previous testResourceGroups', () => {
    const testId = 'test1';
    component.testPlans = [
      {
        test_run_sequences: [
          {
            test_run_configs: [{test_id: testId}],
          },
        ],
      } as unknown as TestPlan,
    ];
    component.tests = {
      [testId]: {name: 'Test 1', test_resource_defs: []} as unknown as Test,
    };

    component.initResourceSettings();
    expect(component.testResourceGroups.length).toBe(1);

    component.initResourceSettings();
    expect(component.testResourceGroups.length).toBe(1);
  });

  describe('schedules', () => {
    const LABEL = 'label1';
    const LOCAL_TZ = 'Asia/Taipei';
    let scheduledPlan: TestPlan;
    let unscheduledPlan: TestPlan;

    beforeEach(() => {
      scheduledPlan = {
        id: '1',
        name: 'plan1',
        labels: [LABEL],
        cron_exp: '0 0 1 1 *',
        cron_exp_timezone: 'America/Los_Angeles',
      } as unknown as TestPlan;
      // Never scheduled plans use the backend default timezone.
      unscheduledPlan = {
        id: '2',
        name: 'plan2',
        labels: [LABEL],
        cron_exp: '',
        cron_exp_timezone: 'UTC',
      } as unknown as TestPlan;
      (mttClient.getTestPlans as jasmine.Spy).and.returnValue(observableOf({
        test_plans: [
          scheduledPlan,
          unscheduledPlan,
          {id: '3', name: 'other', labels: ['other']},
        ],
      }));
      component.localTimezone = LOCAL_TZ;
      component.loadTestPlans(LABEL);
    });

    function getScheduleTimeForm(): ScheduleTimeForm {
      fixture.detectChanges();
      return fixture.debugElement.query(By.directive(ScheduleTimeForm))
          .componentInstance as ScheduleTimeForm;
    }

    it('loadTestPlans should initialize schedule properties', () => {
      expect(component.testPlans).toEqual([scheduledPlan, unscheduledPlan]);
      expect(component.originalCronExps.get('1')).toBe('0 0 1 1 *');
      expect(component.originalCronExps.get('2')).toBe('');
      expect(component.originalTimezones.get('1'))
          .toBe('America/Los_Angeles');
      expect(component.originalTimezones.get('2')).toBe('UTC');
      expect(component.selectedScheduleType).toBe('');
      expect(component.batchCronExp).toBeNull();
      expect(component.batchTimezone).toBe(LOCAL_TZ);
    });

    it('loadTestPlans should reset batch inputs when reloading', () => {
      component.selectedScheduleType = ScheduleType.CUSTOM;
      component.batchCronExp = '0 * * * *';
      component.batchTimezone = 'UTC';

      component.loadTestPlans(LABEL);

      expect(component.selectedScheduleType).toBe('');
      expect(component.batchCronExp).toBeNull();
      expect(component.batchTimezone).toBe(LOCAL_TZ);
    });

    it('Keep Original should leave cron expressions and timezones unchanged',
       () => {
         // Apply a schedule, then switch back to keep original.
         component.selectedScheduleType = ScheduleType.PERIODIC;
         component.batchCronExp = '15 * * * *';
         component.updateBatchSchedule();

         component.selectedScheduleType = '';
         component.batchCronExp = null;
         component.updateBatchSchedule();

         expect(scheduledPlan.cron_exp).toBe('0 0 1 1 *');
         expect(scheduledPlan.cron_exp_timezone).toBe('America/Los_Angeles');
         expect(unscheduledPlan.cron_exp).toBe('');
         expect(unscheduledPlan.cron_exp_timezone).toBe('UTC');
       });

    it('Manual should clear cron expressions and keep timezones', () => {
      component.selectedScheduleType = ScheduleType.MANUAL;
      component.batchCronExp = '';
      component.updateBatchSchedule();

      expect(scheduledPlan.cron_exp).toBe('');
      expect(scheduledPlan.cron_exp_timezone).toBe('America/Los_Angeles');
      expect(unscheduledPlan.cron_exp).toBe('');
      expect(unscheduledPlan.cron_exp_timezone).toBe('UTC');
    });

    it('Periodic should apply cron and local timezone to all plans by default',
       () => {
         component.selectedScheduleType = ScheduleType.PERIODIC;
         component.batchCronExp = '30 8 * * 3';
         component.updateBatchSchedule();

         expect(scheduledPlan.cron_exp).toBe('30 8 * * 3');
         expect(scheduledPlan.cron_exp_timezone).toBe(LOCAL_TZ);
         expect(unscheduledPlan.cron_exp).toBe('30 8 * * 3');
         expect(unscheduledPlan.cron_exp_timezone).toBe(LOCAL_TZ);
       });

    it('Custom should apply cron and the chosen timezone to all plans', () => {
      component.selectedScheduleType = ScheduleType.CUSTOM;
      component.batchCronExp = '50 19 20 1 *';
      component.batchTimezone = 'UTC';
      component.updateBatchSchedule();

      expect(scheduledPlan.cron_exp).toBe('50 19 20 1 *');
      expect(scheduledPlan.cron_exp_timezone).toBe('UTC');
      expect(unscheduledPlan.cron_exp).toBe('50 19 20 1 *');
      expect(unscheduledPlan.cron_exp_timezone).toBe('UTC');
    });

    it('Custom with an empty cron expression should keep original values',
       () => {
         component.selectedScheduleType = ScheduleType.CUSTOM;
         component.batchCronExp = '50 19 20 1 *';
         component.updateBatchSchedule();

         component.batchCronExp = '';
         component.updateBatchSchedule();

         expect(scheduledPlan.cron_exp).toBe('0 0 1 1 *');
         expect(scheduledPlan.cron_exp_timezone).toBe('America/Los_Angeles');
         expect(unscheduledPlan.cron_exp).toBe('');
         expect(unscheduledPlan.cron_exp_timezone).toBe('UTC');
       });

    it('should use schedule-time-form with a Keep Original option', () => {
      const form = getScheduleTimeForm();

      expect(form.allowKeepOriginal).toBe(true);
      expect(form.timezone).toBe(LOCAL_TZ);
    });

    it('should apply changes made in schedule-time-form', () => {
      const form = getScheduleTimeForm();

      // Periodic without touching the timezone uses the local timezone.
      form.selectedPeriodicType = PeriodicType.DAY;
      form.selectedHour = 19;
      form.selectedMinute = 50;
      form.changeScheduleType(ScheduleType.PERIODIC);
      expect(component.selectedScheduleType).toBe(ScheduleType.PERIODIC);
      expect(component.batchCronExp).toBe('50 19 * * *');
      expect(scheduledPlan.cron_exp).toBe('50 19 * * *');
      expect(scheduledPlan.cron_exp_timezone).toBe(LOCAL_TZ);
      expect(unscheduledPlan.cron_exp).toBe('50 19 * * *');
      expect(unscheduledPlan.cron_exp_timezone).toBe(LOCAL_TZ);

      // Changing the timezone applies it to all plans.
      form.timezoneChange.emit('UTC');
      expect(component.batchTimezone).toBe('UTC');
      expect(scheduledPlan.cron_exp_timezone).toBe('UTC');
      expect(unscheduledPlan.cron_exp_timezone).toBe('UTC');

      // Manual clears the cron expressions and restores timezones.
      form.changeScheduleType(ScheduleType.MANUAL);
      expect(component.selectedScheduleType).toBe(ScheduleType.MANUAL);
      expect(scheduledPlan.cron_exp).toBe('');
      expect(scheduledPlan.cron_exp_timezone).toBe('America/Los_Angeles');
      expect(unscheduledPlan.cron_exp).toBe('');
      expect(unscheduledPlan.cron_exp_timezone).toBe('UTC');

      // Keep Original restores everything.
      form.changeScheduleType('');
      expect(component.selectedScheduleType).toBe('');
      expect(component.batchCronExp).toBeNull();
      expect(scheduledPlan.cron_exp).toBe('0 0 1 1 *');
      expect(scheduledPlan.cron_exp_timezone).toBe('America/Los_Angeles');
      expect(unscheduledPlan.cron_exp).toBe('');
      expect(unscheduledPlan.cron_exp_timezone).toBe('UTC');
    });

    it('should restore undefined schedule fields', () => {
      const legacyPlan = {id: '4', name: 'legacy', labels: [LABEL]} as
          unknown as TestPlan;
      (mttClient.getTestPlans as jasmine.Spy).and.returnValue(observableOf({
        test_plans: [legacyPlan],
      }));
      component.loadTestPlans(LABEL);

      // Keep original
      component.updateBatchSchedule();
      expect(legacyPlan.cron_exp).toBeUndefined();
      expect(legacyPlan.cron_exp_timezone).toBeUndefined();

      // Periodic, then back to keep original
      component.selectedScheduleType = ScheduleType.PERIODIC;
      component.batchCronExp = '0 * * * *';
      component.updateBatchSchedule();
      expect(legacyPlan.cron_exp).toBe('0 * * * *');
      expect(legacyPlan.cron_exp_timezone).toBe(LOCAL_TZ);

      component.selectedScheduleType = '';
      component.batchCronExp = null;
      component.updateBatchSchedule();
      expect(legacyPlan.cron_exp).toBeUndefined();
      expect(legacyPlan.cron_exp_timezone).toBeUndefined();

      // Manual only sets the cron expression
      component.selectedScheduleType = ScheduleType.MANUAL;
      component.batchCronExp = '';
      component.updateBatchSchedule();
      expect(legacyPlan.cron_exp).toBe('');
      expect(legacyPlan.cron_exp_timezone).toBeUndefined();
    });

    it('should skip test plans without an ID', () => {
      const planWithoutId = {
        name: 'no_id',
        labels: [LABEL],
        cron_exp: '0 0 * * *',
        cron_exp_timezone: 'UTC',
      } as unknown as TestPlan;
      (mttClient.getTestPlans as jasmine.Spy).and.returnValue(observableOf({
        test_plans: [scheduledPlan, planWithoutId],
      }));
      component.loadTestPlans(LABEL);

      component.selectedScheduleType = ScheduleType.PERIODIC;
      component.batchCronExp = '0 * * * *';
      component.updateBatchSchedule();

      expect(scheduledPlan.cron_exp).toBe('0 * * * *');
      expect(planWithoutId.cron_exp).toBe('0 0 * * *');
      expect(planWithoutId.cron_exp_timezone).toBe('UTC');
    });

    it('should offer the original timezones', () => {
      expect(component.originalTimezoneOptions).toEqual([
        'America/Los_Angeles', 'UTC'
      ]);

      const form = getScheduleTimeForm();
      expect(form.extraTimezones).toEqual(['America/Los_Angeles', 'UTC']);
      expect(form.timezoneOptions).toContain('America/Los_Angeles');
      expect(form.timezoneOptions).toContain('UTC');
      expect(form.timezoneOptions).toContain(LOCAL_TZ);
    });

    it('should show a hint if the cron expression is empty', () => {
      const hint = () =>
          (fixture.nativeElement as HTMLElement).querySelector('.empty-cron-hint');
      fixture.detectChanges();
      expect(hint()).toBeNull();

      component.selectedScheduleType = ScheduleType.CUSTOM;
      component.batchCronExp = '';
      fixture.detectChanges();
      expect(hint()!.textContent)
          .toContain('Empty cron expression: original schedules will be kept.');

      component.batchCronExp = '0 * * * *';
      fixture.detectChanges();
      expect(hint()).toBeNull();

      component.selectedScheduleType = ScheduleType.MANUAL;
      component.batchCronExp = '';
      fixture.detectChanges();
      expect(hint()).toBeNull();
    });

    it('should show Keep Original and hide the timezone initially and after reload',
       async () => {
         const getSelects = () =>
             fixture.debugElement.query(By.css('schedule-time-form'))
                 .queryAll(By.css('.schedule mat-select'));
         const form = getScheduleTimeForm();
         await fixture.whenStable();
         fixture.detectChanges();
         expect(form.selectedScheduleType).toBe('');
         expect(getSelects().length).toBe(1);  // no timezone select
         expect(getSelects()[0].nativeElement.textContent)
             .toContain('-- Keep Original --');

         // Select periodic, the timezone select is shown
         form.selectedScheduleType = ScheduleType.PERIODIC;
         form.changeScheduleType(ScheduleType.PERIODIC);
         fixture.detectChanges();
         await fixture.whenStable();
         fixture.detectChanges();
         expect(component.batchCronExp).toBe('0 * * * *');
         expect(getSelects().length).toBe(2);

         // Reloading resets the form to keep original
         component.loadTestPlans(LABEL);
         fixture.detectChanges();
         await fixture.whenStable();
         fixture.detectChanges();
         expect(form.selectedScheduleType).toBe('');
         expect(getSelects().length).toBe(1);
         expect(getSelects()[0].nativeElement.textContent)
             .toContain('-- Keep Original --');
       });
  });

  it('combineResources should preserve properties from sampleConfig', () => {
    const test: Test = {
      name: 'Test 1',
      test_resource_defs: [{
        name: 'res1',
        test_resource_type: TestResourceType.DEVICE_IMAGE,
        decompress: false,
      }],
    };
    const sampleConfig: TestRunConfig = {
      test_id: 'test1',
      test_resource_objs: [{
        name: 'res1',
        url: 'http://old',
        decompress: true,
      }],
    } as unknown as TestRunConfig;

    const result = component.combineResources(test, sampleConfig);

    expect(result.length).toBe(1);
    expect(result[0].name).toBe('res1');
    expect(result[0].url).toBe('');
    expect(result[0].decompress).toBe(true);
  });

  it('update should update other properties but preserve URL if new URL is empty',
     () => {
       const testId = 'test1';
       const config = {
         test_id: testId,
         test_resource_objs:
             [{name: 'res1', url: 'http://original', decompress: false}]
       };
       component.testPlans =
           [{id: '1', test_run_sequences: [{test_run_configs: [config]}]} as
            unknown as TestPlan];

       component.testResourceGroups = [{
         testId,
         testName: 'Test 1',
         resources: [{name: 'res1', url: '', decompress: true}]
       }];

       (mttClient.updateTestPlans as jasmine.Spy)
           .and.returnValue(observableOf({}));

       component.update();

       expect(config.test_resource_objs[0].url).toBe('http://original');
       expect(config.test_resource_objs[0].decompress).toBe(true);
       expect(mttClient.updateTestPlans).toHaveBeenCalled();
     });

  it('update should not add resource if it does not exist in target config',
     () => {
       const testId = 'test1';
       const config = {
         test_id: testId,
         test_resource_objs: [] as TestResourceObj[],
       } as unknown as TestRunConfig;
       component.testPlans =
           [{id: '1', test_run_sequences: [{test_run_configs: [config]}]}] as
           unknown as TestPlan[];

       component.testResourceGroups = [{
         testId,
         testName: 'Test 1',
         resources: [{name: 'res1', url: 'http://new'}]
       }];

       (mttClient.updateTestPlans as jasmine.Spy)
           .and.returnValue(observableOf({}));

       component.update();

       expect(config.test_resource_objs!.length).toBe(0);
       expect(mttClient.updateTestPlans).toHaveBeenCalled();
     });

  it('mergeConfigResources should update existing resources but not add new ones',
     () => {
       const config = {
         test_id: 'test1',
         test_resource_objs: [
           {name: 'res1', url: 'http://old'},
         ]
       } as unknown as TestRunConfig;

       const newResources = [
         {name: 'res1', url: 'http://new'},
         {name: 'res2', url: 'http://new'},
       ];

       component.mergeConfigResources(config, newResources);

       expect(config.test_resource_objs!.length).toBe(1);
       expect(config.test_resource_objs![0].name).toBe('res1');
       expect(config.test_resource_objs![0].url).toBe('http://new');
     });
});
