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

import {DebugElement} from '@angular/core';
import {ComponentFixture, inject, TestBed} from '@angular/core/testing';
import {NoopAnimationsModule} from '@angular/platform-browser/animations';
import {provideRouter, Router} from '@angular/router';
import {EMPTY, of as observableOf} from 'rxjs';

import {MttClient} from '../services/mtt_client';
import {TestPackageInfo, TestRunState, TestRunSummary} from '../services/mtt_models';
import {Notifier} from '../services/notifier';
import {DeviceInfo} from '../services/tfc_models';
import {DEFAULT_PAGE_SIZE} from '../shared/paginator';
import {getEl, getEls, getTextContent} from '../testing/jasmine_util';
import {newMockDeviceInfo} from '../testing/mtt_lab_mocks';
import {newMockTestPackageInfo, toTitleCase} from '../testing/mtt_mocks';

import {TestRunList} from './test_run_list';
import {TestRunsModule} from './test_runs_module';

describe('TestRunList', () => {
  let testRunList: TestRunList;
  let testRunListFixture: ComponentFixture<TestRunList>;
  let mttClient: jasmine.SpyObj<MttClient>;
  let notifier: jasmine.SpyObj<Notifier>;
  let testDevices: DeviceInfo[];
  let testPackageInfo: TestPackageInfo;
  let testRunCompleted: TestRunSummary;
  let testRunPending: TestRunSummary;
  let el: DebugElement;

  beforeEach(() => {
    window.localStorage.clear();
    testDevices = [newMockDeviceInfo()];
    testPackageInfo = newMockTestPackageInfo();

    testRunCompleted = {
      id: 'completed',
      device_specs: ['device_serial:target1', 'device_serial:target2'],
      state: TestRunState.COMPLETED,
      test_name: 'test_name',
      test_package_info: testPackageInfo,
      test_devices: testDevices,
    };

    testRunPending = {
      id: 'pending',
      device_specs: ['device_serial:target1', 'device_serial:target2'],
      state: TestRunState.PENDING,
      test_name: 'test_name',
      test_package_info: testPackageInfo,
      test_devices: testDevices,
    };

    mttClient =
        jasmine.createSpyObj('mttClient', ['getTestRuns', 'deleteTestRuns']);
    mttClient.deleteTestRuns.and.returnValue(EMPTY);
    mttClient.getTestRuns.and.returnValue(
        observableOf({test_runs: [testRunCompleted, testRunPending]}));

    notifier = jasmine.createSpyObj(['confirm', 'showError']);

    TestBed.configureTestingModule({
      imports: [NoopAnimationsModule, TestRunsModule],
      providers: [
        provideRouter([]),
        {provide: MttClient, useValue: mttClient},
        {provide: Notifier, useValue: notifier},
      ],
    });

    testRunListFixture = TestBed.createComponent(TestRunList);
    testRunListFixture.detectChanges();
    el = testRunListFixture.debugElement;
    testRunList = testRunListFixture.componentInstance;
  });

  it('gets initialized', () => {
    expect(testRunList).toBeTruthy();
  });

  it('calls the mtt client api method getTestRuns', async () => {
    await testRunListFixture.whenStable();  // load() is called asynchronously
    expect(mttClient.getTestRuns).toHaveBeenCalled();
  });

  it('displays the correct test run values', async () => {
    await testRunListFixture.whenStable();  // load() is called asynchronously
    testRunListFixture.detectChanges();

    const text = getTextContent(el);
    const device = testRunCompleted.test_devices![0];

    expect(text).toContain('test_name');
    expect(text).toContain(toTitleCase(TestRunState.COMPLETED));
    expect(text).toContain(toTitleCase(TestRunState.PENDING));
    expect(text).toContain(
        `${testPackageInfo.name} ${testPackageInfo.version}`);

    expect(text).toContain('device_serial:target1');
    expect(text).toContain(device.build_id!);
    expect(text).toContain(device.product);
  });

  it('can load previous page of test runs', () => {
    testRunList.prevPageToken = 'prev';
    testRunList.nextPageToken = 'next';
    testRunList.load(true);
    expect(mttClient.getTestRuns)
        .toHaveBeenCalledWith(DEFAULT_PAGE_SIZE, 'prev', true, [], []);
  });

  it('can load next page of test runs', () => {
    testRunList.prevPageToken = 'prev';
    testRunList.nextPageToken = 'next';
    testRunList.load(false);
    expect(mttClient.getTestRuns)
        .toHaveBeenCalledWith(DEFAULT_PAGE_SIZE, 'next', false, [], []);
  });

  it('can handle page size change', () => {
    testRunList.prevPageToken = 'prev';
    testRunList.nextPageToken = 'next';
    testRunList.paginator.changePageSize(20);
    expect(mttClient.getTestRuns)
        .toHaveBeenCalledWith(20, undefined, false, [], []);
  });

  it('can update pagination parameters', inject([Router], (router: Router) => {
       spyOn(router, 'navigate');
       mttClient.getTestRuns.and.returnValue(observableOf(
           {test_runs: [], prev_page_token: 'prev', next_page_token: 'next'}));

       testRunList.load();
       expect(testRunList.prevPageToken).toEqual('prev');
       expect(testRunList.nextPageToken).toEqual('next');
       expect(testRunList.paginator.hasPrevious).toBeTruthy();
       expect(testRunList.paginator.hasNext).toBeTruthy();
       expect(router.navigate).toHaveBeenCalledWith([], {
         queryParams: {page: 'prev', size: null, filter: null, state: null}
       });
     }));

  it('should hide column on view_columns dropdown menu button clicked', () => {
    getEl(el, '.view_columns_btn').click();

    const removableColumns = testRunList.columns.filter((c) => c.removable);
    const column = removableColumns[0];
    getEl(el, '#' + column.fieldName + '_menu_btn').click();
    testRunListFixture.detectChanges();
    el = testRunListFixture.debugElement;
    expect(getEls(el, 'mat-header-cell').length)
        .toBe(testRunList.columns.length - 1);
  });

  it('can handle filter function', () => {
    testRunList.filters = ['device_id'];
    testRunList.load(false);
    expect(mttClient.getTestRuns)
        .toHaveBeenCalledWith(
            testRunList.PAGE_SIZE_OPTIONS[0], undefined, false, ['device_id'],
            []);
  });

  it('can update filter parameters', inject([Router], (router: Router) => {
       spyOn(router, 'navigate');
       mttClient.getTestRuns.and.returnValue(observableOf(
           {test_runs: [], prev_page_token: 'prev', next_page_token: 'next'}));
       testRunList.filters = ['device_id'];
       testRunList.load();
       expect(router.navigate).toHaveBeenCalledWith([], {
         queryParams:
             {page: 'prev', size: null, filter: ['device_id'], state: null}
       });
     }));

  it('can handle states', () => {
    testRunList.states = [TestRunState.COMPLETED];
    testRunList.load(false);
    expect(mttClient.getTestRuns)
        .toHaveBeenCalledWith(
            testRunList.PAGE_SIZE_OPTIONS[0], undefined, false, [],
            [TestRunState.COMPLETED]);
  });

  it('can update filter parameters', inject([Router], (router: Router) => {
       spyOn(router, 'navigate');
       mttClient.getTestRuns.and.returnValue(observableOf(
           {test_runs: [], prev_page_token: 'prev', next_page_token: 'next'}));
       testRunList.states = [TestRunState.COMPLETED];
       testRunList.load();
       expect(router.navigate).toHaveBeenCalledWith([], {
         queryParams: {
           page: 'prev',
           size: null,
           filter: null,
           state: [TestRunState.COMPLETED]
         }
       });
     }));

  it('can delete test runs', () => {
    testRunList.prevPageToken = 'prev';
    testRunList.nextPageToken = 'next';
    notifier.confirm.and.returnValue(observableOf(true));  // confirm delete

    testRunList.selection.select(testRunCompleted);
    testRunListFixture.detectChanges();
    getEl(el, '.delete-button').click();
    expect(mttClient.deleteTestRuns).toHaveBeenCalledWith(['completed']);
    // Reloads current page (previous page token with backwards == false)
    expect(mttClient.getTestRuns)
        .toHaveBeenCalledWith(DEFAULT_PAGE_SIZE, 'prev', false, [], []);
  });

  it('cannot delete non-final test runs', () => {
    notifier.confirm.and.returnValue(observableOf(true));  // confirm delete
    mttClient.getTestRuns.and.returnValue(
        observableOf({test_runs: [testRunPending]}));
    testRunList.load();
    testRunListFixture.detectChanges();

    testRunList.toggleSelection();
    testRunListFixture.detectChanges();

    expect(getEl(el, '.delete-button').getAttribute('disabled')).toBeTruthy();
  });
});
