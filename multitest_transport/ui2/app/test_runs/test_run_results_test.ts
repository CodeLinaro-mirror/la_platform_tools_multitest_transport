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
import {ComponentFixture, TestBed} from '@angular/core/testing';
import {NoopAnimationsModule} from '@angular/platform-browser/animations';

import {InvocationStatus} from '../services/tfc_models';
import {getTextContent} from '../testing/jasmine_util';
import {newMockInvocationStatus} from '../testing/mtt_mocks';
import {TestRunResults} from './test_run_results';
import {TestRunsModule} from './test_runs_module';

describe('TestRunResults', () => {
  let testRunResults: TestRunResults;
  let testRunResultsFixture: ComponentFixture<TestRunResults>;
  let el: DebugElement;

  let invocationStatus: InvocationStatus;

  beforeEach(() => {
    invocationStatus = newMockInvocationStatus();
    TestBed.configureTestingModule({
      imports: [NoopAnimationsModule, TestRunsModule],
    });
    testRunResultsFixture = TestBed.createComponent(TestRunResults);
    testRunResults = testRunResultsFixture.componentInstance;
    el = testRunResultsFixture.debugElement;
    testRunResults.invocationStatus = invocationStatus;
    testRunResultsFixture.detectChanges();
  });

  it('displays the table headers and data', () => {
    const textContent = getTextContent(el);
    expect(textContent).toContain('Name');
    expect(textContent).toContain('Result');
    expect(textContent).toContain('Run Time');
    expect(textContent).toContain('FAILED (29/42)');
    expect(textContent).toContain('00:00:12');

    // TODO: Add more values after default-expanded enabled
  });
});
