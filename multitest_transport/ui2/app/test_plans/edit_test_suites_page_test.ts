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
import {NoopAnimationsModule} from '@angular/platform-browser/animations';
import {ActivatedRoute} from '@angular/router';
import {Observable, of as observableOf} from 'rxjs';

import {MttClient} from '../services/mtt_client';
import {NameValuePair, Test, TestPlan, TestRunAction} from '../services/mtt_models';
import {Notifier} from '../services/notifier';

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
    component.actionsFormGroup.addControl('1', new UntypedFormControl());

    component.initActionSettings();

    expect(component.actionRefsMap.size).toBe(0);
    expect(component.referencedActions).toEqual([]);
    expect(component.effectiveOptionDefs).toEqual({});
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

  it('initResourceSettings should populate testResourceGroups', () => {
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
    expect(component.testResourceGroups[0].testId).toBe(testId);
    expect(component.testResourceGroups[0].testName).toBe('Test 1');
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

  it('loadTestPlans should filter custom schedules and initialize properties',
     () => {
       const label = 'label1';
       const testPlans = [
         {
           id: '1',
           name: 'plan1',
           labels: [label],
           cron_exp: '0 0 1 1 *',
           cron_exp_timezone: 'UTC',
         },
         {
           id: '2',
           name: 'plan2',
           labels: [label],
           cron_exp: '0 * * * *',
         },
         {
           id: '3',
           name: 'plan3',
           labels: [label],
           cron_exp: '',
         },
       ] as unknown as TestPlan[];
       (mttClient.getTestPlans as jasmine.Spy).and.returnValue(observableOf({
         test_plans: testPlans
       }));

       component.loadTestPlans(label);

       expect(component.testPlans.length).toBe(3);
       expect(component.customScheduleTestPlans.length).toBe(1);
       expect(component.customScheduleTestPlans[0].id).toBe('1');
       expect(component.originalCronExps.get('1')).toBe('0 0 1 1 *');
       expect(component.originalTimezones.get('1')).toBe('UTC');
       expect(component.batchCronExp).toBe('');
       expect(component.batchTimezone).toBe('');
       expect(component.timezoneOptions).toContain('UTC');
     });

  it('updateBatchSchedule should update custom schedule test plans', () => {
    const plan1 = {
      id: '1',
      cron_exp: 'old_cron',
      cron_exp_timezone: 'old_tz',
    } as unknown as TestPlan;
    component.customScheduleTestPlans = [plan1];
    component.originalCronExps.set('1', 'old_cron');
    component.originalTimezones.set('1', 'old_tz');

    component.batchCronExp = 'new_cron';
    component.batchTimezone = 'new_tz';
    component.updateBatchSchedule();

    expect(plan1.cron_exp).toBe('new_cron');
    expect(plan1.cron_exp_timezone).toBe('new_tz');
  });

  it('updateBatchSchedule should restore original values when batch inputs are empty',
     () => {
       const plan1 = {
         id: '1',
         cron_exp: 'new_cron',
         cron_exp_timezone: 'new_tz',
       } as unknown as TestPlan;
       component.customScheduleTestPlans = [plan1];
       component.originalCronExps.set('1', 'old_cron');
       component.originalTimezones.set('1', 'old_tz');

       component.batchCronExp = '';
       component.batchTimezone = '';
       component.updateBatchSchedule();

       expect(plan1.cron_exp).toBe('old_cron');
       expect(plan1.cron_exp_timezone).toBe('old_tz');
     });

  it('loadTestPlans should reset batch inputs when reloading', () => {
    const label1 = 'label1';
    (mttClient.getTestPlans as jasmine.Spy)
        .and.returnValue(observableOf({test_plans: []}));
    component.loadTestPlans(label1);

    component.batchCronExp = '0 * * * *';
    component.batchTimezone = 'UTC';

    const label2 = 'label2';
    component.loadTestPlans(label2);

    expect(component.batchCronExp).toBe('');
    expect(component.batchTimezone).toBe('');
  });
});
