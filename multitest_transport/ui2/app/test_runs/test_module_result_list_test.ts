/**
 * Copyright 2021 Google LLC
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
import {ComponentFixture, TestBed} from '@angular/core/testing';
import {NoopAnimationsModule} from '@angular/platform-browser/animations';
import {of as observableOf} from 'rxjs';

import {MttClient, TestResultClient} from '../services/mtt_client';
import {TestCaseResult, TestModuleResult, TestStatus} from '../services/mtt_models';
import {Notifier} from '../services/notifier';
import {getEl, getEls, getTextContent} from '../testing/jasmine_util';
import {newMockTestCaseResult, newMockTestModuleResult} from '../testing/mtt_mocks';

import {TestModuleResultList} from './test_module_result_list';
import {TestRunsModule} from './test_runs_module';

describe('TestModuleResultList', () => {
  let testResultModuleList: TestModuleResultList;
  let testResultModuleListFixture: ComponentFixture<TestModuleResultList>;
  let client: jasmine.SpyObj<TestResultClient>;
  let notifier: jasmine.SpyObj<Notifier>;
  let el: DebugElement;

  let module1: TestModuleResult;
  let module2: TestModuleResult;
  let modules: TestModuleResult[] = [];
  let testCase1: TestCaseResult;
  let testCase2: TestCaseResult;
  let testCase3: TestCaseResult;
  let testCases: TestCaseResult[] = [];
  const testRunId = 'test-run-id';

  beforeEach(() => {
    notifier = jasmine.createSpyObj(['showError']);

    module1 = newMockTestModuleResult('module.1', 'Module 1', 123, 456, 789);
    module2 = newMockTestModuleResult('m_2', 'Second Module', 0, 0, 0);
    modules = [module1, module2];

    testCase1 = newMockTestCaseResult(
        'module.1', 'test_case.1', TestStatus.PASS, '', '');
    testCase2 = newMockTestCaseResult(
        'module.1', 'test_case2', TestStatus.FAIL, 'some failure message',
        'some stack trace');
    testCase3 = newMockTestCaseResult(
        'module.1', 'really_really_long.test.case.name_with_lots_of_text',
        TestStatus.ASSUMPTION_FAILURE,
        'some other failure message that is really really really long',
        'some really really really really really really really really really really really really long stack trace');
    testCases = [testCase1, testCase2, testCase3];

    client = jasmine.createSpyObj(['listModules', 'listTestCases']);
    client.listModules.and.returnValue(
        observableOf({results: modules, next_page_token: 'modules:page'}));
    client.listTestCases.and.returnValue(
        observableOf({results: testCases, next_page_token: 'page:token'}));

    TestBed.configureTestingModule({
      imports: [NoopAnimationsModule, TestRunsModule],
      providers: [
        {provide: MttClient, useValue: {testResults: client}},
        {provide: Notifier, useValue: notifier},
      ],
    });
    testResultModuleListFixture = TestBed.createComponent(TestModuleResultList);
    testResultModuleList = testResultModuleListFixture.componentInstance;
    el = testResultModuleListFixture.debugElement;
    testResultModuleList.testRunId = testRunId;
    testResultModuleList.loadModules();
    testResultModuleListFixture.detectChanges();
  });

  it('displays the module results', () => {
    const textContent = getTextContent(el);
    expect(textContent).toContain('Module 1');
    expect(textContent).toContain('Second Module');

    expect(textContent).toContain('warning 456/789');  // Module 1 failed/total
    expect(textContent).toContain('0/0');
    expect(textContent).toContain('00:00:00'); // Default duration
    expect(textContent).not.toContain('null');
  });

  it('displays modules in the order received from backend', () => {
    // Backend sorts: incomplete first, then default order
    const m3 = newMockTestModuleResult(
      'm3',
      'C Module',
      0,
      0,
      1,
      undefined,
      0,
      false,
    );
    const m1 = newMockTestModuleResult(
      'm1',
      'B Module',
      1,
      0,
      1,
      undefined,
      0,
      true,
    );
    const m2 = newMockTestModuleResult(
      'm2',
      'A Module',
      1,
      0,
      1,
      undefined,
      0,
      true,
    );

    client.listModules.and.returnValue(observableOf({results: [m3, m1, m2]}));
    testResultModuleList.moduleResultNodes = [];
    testResultModuleList.loadModules();
    testResultModuleListFixture.detectChanges();

    const moduleNames = getEls(el, '.module-name').map((e) =>
      e.textContent!.trim(),
    );
    expect(moduleNames).toEqual(['C Module', 'B Module', 'A Module']);
  });

  it('displays the test case results', () => {
    getEl(el, '.expand-button').click();
    testResultModuleListFixture.detectChanges();

    const textContent = getTextContent(el);
    expect(textContent).toContain('test_case.1');
    expect(textContent).toContain('test_case2');
    expect(textContent)
        .toContain('really_really_long.test.case.name_with_lots_of_text');

    expect(textContent).toContain('some failure message');
    expect(textContent)
        .toContain(
            'some other failure message that is really really really long');

    expect(textContent).toContain('Load more test cases');
  });

  it('can load more test case results', () => {
    getEl(el, '.expand-button').click();
    testResultModuleListFixture.detectChanges();

    // Set next page of test case results
    const testCase4 = newMockTestCaseResult(
        'module.1', 'test.case.Four', TestStatus.UNKNOWN, '', '');
    const testCase5 = newMockTestCaseResult(
        'module.1', 'test_case_5', TestStatus.IGNORED, '', '');
    client.listTestCases.and.returnValue(
        observableOf({results: [testCase4, testCase5]}));

    getEl(el, '.load-test-cases-button').click();
    testResultModuleListFixture.detectChanges();

    const textContent = getTextContent(el);

    // First page should still be there
    expect(textContent).toContain('test_case.1');
    expect(textContent).toContain('test_case2');

    expect(textContent).toContain('test.case.Four');
    expect(textContent).toContain('test_case_5');

    expect(textContent).not.toContain('Load more test cases');
  });

  it('opens the stack trace dialog', () => {
    getEl(el, '.expand-button').click();
    testResultModuleListFixture.detectChanges();
    getEl(el, '.stack-trace-button').click();
    testResultModuleListFixture.detectChanges();
    expect(notifier.showError)
        .toHaveBeenCalledWith(
            'test_case2', {
              message: 'some failure message',
              stacktrace: 'some stack trace',
            },
            'Error message');
  });
});
