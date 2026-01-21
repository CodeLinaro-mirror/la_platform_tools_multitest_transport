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
import {DebugElement} from '@angular/core';
import {ComponentFixture, TestBed} from '@angular/core/testing';
import {NoopAnimationsModule} from '@angular/platform-browser/animations';
import {provideRouter, Router} from '@angular/router';
import {of as observableOf} from 'rxjs';

import {MttClient} from '../services/mtt_client';
import {getEl, getEls, getTextContent} from '../testing/jasmine_util';
import {newMockTestPlan} from '../testing/mtt_mocks';

import {TestPlanList} from './test_plan_list';
import {TestPlansModule} from './test_plans_module';

describe('TestPlanList', () => {
  const TEST_PLANS = {
    test_plans: [
      newMockTestPlan('test_plan_id_1', 'test_plan_name_1'),
      newMockTestPlan('test_plan_id_2', 'test_plan_name_2')
    ]
  };

  let testPlanList: TestPlanList;
  let testPlanListFixture: ComponentFixture<TestPlanList>;
  let mttClient: jasmine.SpyObj<MttClient>;
  let el: DebugElement;
  let liveAnnouncer: jasmine.SpyObj<LiveAnnouncer>;

  beforeEach(() => {
    liveAnnouncer =
        jasmine.createSpyObj('liveAnnouncer', ['announce', 'clear']);
    mttClient = jasmine.createSpyObj(
        'mttClient', ['getTestPlans', 'deleteTestPlan', 'runTestPlan']);
    mttClient.getTestPlans.and.returnValue(observableOf(TEST_PLANS));
    mttClient.deleteTestPlan.and.returnValue(observableOf({}));
    mttClient.runTestPlan.and.returnValue(observableOf({}));

    TestBed.configureTestingModule({
      imports: [
        NoopAnimationsModule,
        TestPlansModule,
      ],
      providers: [
        provideRouter([]),
        {provide: LiveAnnouncer, useValue: liveAnnouncer},
        {provide: MttClient, useValue: mttClient},
      ],
    });

    testPlanListFixture = TestBed.createComponent(TestPlanList);
    testPlanListFixture.detectChanges();
    el = testPlanListFixture.debugElement;
    testPlanList = testPlanListFixture.componentInstance;
  });

  it('displays and announces a loading mask', () => {
    expect(liveAnnouncer.announce).toHaveBeenCalledWith('Loading', 'polite');
    expect(liveAnnouncer.announce)
        .toHaveBeenCalledWith('Test plans loaded', 'assertive');
  });

  it('should get initialized correctly', () => {
    expect(testPlanList).toBeTruthy();
  });

  it('should call getTestPlans API correctly', () => {
    expect(mttClient.getTestPlans).toHaveBeenCalled();
  });

  it('should display test plans correctly', () => {
    const textContent = getTextContent(el);
    for (const testPlan of TEST_PLANS.test_plans) {
      expect(textContent).toContain(testPlan.name);
    }
  });

  it('should run a test plan correctly', () => {
    const runTestPlanId = TEST_PLANS.test_plans[0].id;
    getEl(el, '.run-test-plan-button').click();
    expect(mttClient.runTestPlan).toHaveBeenCalledWith(runTestPlanId);
    expect(mttClient.runTestPlan).toHaveBeenCalledTimes(1);
  });

  it('should call confirmDeleteTestPlan correctly', () => {
    spyOn(testPlanList, 'confirmDeleteTestPlan');
    getEl(el, '.menu-button').click();
    getEl(el, '.test-plan-list-delete-btn').click();
    expect(testPlanList.confirmDeleteTestPlan)
        .toHaveBeenCalledWith(TEST_PLANS.test_plans[0]);
    expect(testPlanList.confirmDeleteTestPlan).toHaveBeenCalledTimes(1);
  });

  it('should show correct number of test plan', () => {
    expect(getEls(el, 'mat-row').length).toBe(2);
    testPlanList.deleteTestPlan(TEST_PLANS.test_plans[0]);
    expect(getEls(el, 'mat-row').length).toBe(1);
  });

  it('renders page header correctly', () => {
    const header = getEl(el, 'h1');
    expect(header).toBeTruthy();
    expect(header.innerText).toBe('Test Plans');
  });

  describe('menu button', () => {
    it('should display correct aria-label and tooltip', () => {
      const menuButton = getEl(el, '.menu-button');
      expect(menuButton).toBeTruthy();
      expect(menuButton.getAttribute('aria-label')).toBe('More actions');
      expect(menuButton.getAttribute('mattooltip')).toBe('More actions');
    });
  });

  it('navigateToSuites should navigate to edit test suites page', () => {
    const router = TestBed.inject(Router);
    spyOn(router, 'navigate');
    testPlanList.navigateToSuites('label');
    expect(router.navigate)
        .toHaveBeenCalledWith(
            ['/test_plans/edit_test_suites'],
            {queryParams: {'label': 'label'}});
  });

  describe('label expansion', () => {
    it('should return false for shouldShowExpand when labels are few', () => {
      expect(testPlanList.shouldShowExpand(['l1', 'l2'])).toBe(false);
    });

    it('should return true for shouldShowExpand when labels are many', () => {
      expect(testPlanList.shouldShowExpand([
        'l1', 'l2', 'l3', 'l4'
      ])).toBe(true);
    });

    it('should return true for shouldShowExpand when total length is long',
       () => {
         const longLabel = 'a'.repeat(16);
         expect(testPlanList.shouldShowExpand(['l1', longLabel])).toBe(true);
       });

    it('should return false for shouldShowExpand when total length is short',
       () => {
         const shortLabel = 'a'.repeat(10);
         expect(testPlanList.shouldShowExpand(['l1', shortLabel])).toBe(false);
       });

    it('should return false for shouldShowExpand when labels is undefined',
       () => {
         expect(testPlanList.shouldShowExpand(undefined)).toBe(false);
       });

    it('should return preview labels correctly', () => {
      const labels = ['l1', 'l2', 'l3', 'l4'];
      expect(testPlanList.getPreviewLabels(labels)).toEqual(['l1', 'l2']);
    });

    it('should return empty preview labels if first label is too long', () => {
      const longLabel = 'a'.repeat(16);
      expect(testPlanList.getPreviewLabels([longLabel, 'l2'])).toEqual([]);
    });

    it('should return partial preview labels if combined length is too long',
       () => {
         const l1 = 'a'.repeat(10);
         const l2 = 'b'.repeat(10);
         expect(testPlanList.getPreviewLabels([l1, l2])).toEqual([l1]);
       });

    it('should return empty preview labels when labels is undefined', () => {
      expect(testPlanList.getPreviewLabels(undefined)).toEqual([]);
    });
  });
});
