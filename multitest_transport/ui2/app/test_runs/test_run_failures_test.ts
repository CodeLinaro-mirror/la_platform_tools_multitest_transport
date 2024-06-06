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

import {DebugElement, SimpleChanges} from '@angular/core';
import {ComponentFixture, TestBed} from '@angular/core/testing';
import {NoopAnimationsModule} from '@angular/platform-browser/animations';

import {TestRunState} from '../services/mtt_models';
import {getEl, getTextContent} from '../testing/jasmine_util';

import {TestRunFailures} from './test_run_failures';
import {TestRunsModule} from './test_runs_module';

describe('TestRunFailures', () => {
  let testRunFailures: TestRunFailures;
  let testRunFailuresFixture: ComponentFixture<TestRunFailures>;
  let el: DebugElement;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [
        NoopAnimationsModule,
        TestRunsModule,
      ],
    });
    testRunFailuresFixture = TestBed.createComponent(TestRunFailures);
    el = testRunFailuresFixture.debugElement;
    testRunFailures = testRunFailuresFixture.componentInstance;
  });

  it('gets initialized', () => {
    expect(testRunFailures).toBeTruthy();
  });

  it('displays a checkmark if there is no failure', () => {
    bootstrapStatus(testRunFailures, TestRunState.COMPLETED, 0, 42, 56);
    const text = getTextContent(el);
    expect(text).toContain('0');
    expect(text).toContain('42');
    expect(text).toContain('56');
    expect(getEl(el, 'mat-icon').innerText).toEqual('check_circle');
  });

  it('displays a warning icon if completed with failures', () => {
    bootstrapStatus(testRunFailures, TestRunState.COMPLETED, 13, 42, 56);
    const text = getTextContent(el);
    expect(text).toContain('13');
    expect(text).toContain('42');
    expect(text).toContain('56');
    expect(getEl(el, 'mat-icon').innerText).toEqual('warning');
  });

  it('displays a warning icon if error with no failures', () => {
    bootstrapStatus(testRunFailures, TestRunState.ERROR, 0, 42, 56);
    const text = getTextContent(el);
    expect(text).toContain('0');
    expect(text).toContain('42');
    expect(text).toContain('56');
    expect(getEl(el, 'mat-icon').innerText).toEqual('warning');
  });

  function bootstrapStatus(
      testRunFailures: TestRunFailures, state: TestRunState,
      numFailedTests: number, numTotalTests: number, numFailedModules: number) {
    testRunFailures.state = state;
    testRunFailures.numFailedTests = numFailedTests;
    testRunFailures.numTotalTests = numTotalTests;
    testRunFailures.numFailedModules = numFailedModules;
    testRunFailures.ngOnChanges({} as SimpleChanges);
    testRunFailuresFixture.detectChanges();
  }
});
