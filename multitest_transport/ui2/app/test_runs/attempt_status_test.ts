/**
 * Copyright 2020 Google LLC
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

import {AttemptStatus} from './attempt_status';
import {APP_DATA, AppData} from '../services';
import {Test, TestRun} from '../services/mtt_models';
import {CommandAttempt, CommandState} from '../services/tfc_models';
import {getTextContent} from '../testing/jasmine_util';
import {newMockCommandAttempt, newMockTest, newMockTestRun} from '../testing/mtt_mocks';
import {newMockAppData} from '../testing/mtt_lab_mocks';
import {TestRunsModule} from './test_runs_module';

describe('AttemptStatus', () => {
  let attemptStatus: AttemptStatus;
  let attemptStatusFixture: ComponentFixture<AttemptStatus>;
  let el: DebugElement;

  let appData: AppData;
  let test: Test;
  let testRun: TestRun;
  let attempt: CommandAttempt;

  beforeEach(() => {
    appData = newMockAppData();
    test = newMockTest();
    testRun = newMockTestRun(test);
    attempt = newMockCommandAttempt();
    TestBed.configureTestingModule({
      imports: [NoopAnimationsModule, TestRunsModule],
      providers: [
        {provide: APP_DATA, useValue: appData},
      ]
    });
    attemptStatusFixture = TestBed.createComponent(AttemptStatus);
    attemptStatus = attemptStatusFixture.componentInstance;
    el = attemptStatusFixture.debugElement;
    attemptStatus.testRun = testRun;
    attemptStatus.attempt = attempt;
    attemptStatusFixture.detectChanges();
  });

  it('can init properly', () => {
    expect(attemptStatus).toBeTruthy();
  });

  it('can render queued attempt correctly', () => {
    const attempt = newMockCommandAttempt(
        undefined, undefined, 'request_id', 'command_id', 'attempt_id',
        CommandState.QUEUED);
    attemptStatus.attempt = attempt;
    attemptStatusFixture.detectChanges();
    getTextContent(el).includes('Test is queued.');
  });

  it('can render running attempt correctly', () => {
    const attempt = newMockCommandAttempt(
        undefined, undefined, 'request_id', 'command_id', 'attempt_id',
        CommandState.RUNNING);
    attemptStatus.attempt = attempt;
    attemptStatusFixture.detectChanges();
    getTextContent(el).includes('Test is running.');
  });

  it('can render completed attempt correctly', () => {
    const attempt = newMockCommandAttempt(
        0, 123, 'request_id', 'command_id', 'attempt_id',
        CommandState.COMPLETED);
    attemptStatus.attempt = attempt;
    attemptStatusFixture.detectChanges();
    getTextContent(el).includes('Test completed: 123 tests passed.');
  });

  it('can render completed attempt with failed test cases correctly', () => {
    const attempt = newMockCommandAttempt(
        12, 123, 'request_id', 'command_id', 'attempt_id',
        CommandState.COMPLETED);
    attemptStatus.attempt = attempt;
    attemptStatusFixture.detectChanges();
    getTextContent(el).includes('Test completed: 12/135 tests passed.');
  });

  it('can render error attempt correctly', () => {
    const attempt = newMockCommandAttempt(
        0, 123, 'request_id', 'command_id', 'attempt_id',
        CommandState.ERROR);
    attemptStatus.attempt = attempt;
    attemptStatusFixture.detectChanges();
    getTextContent(el).includes('Test failed to start: error');
  });
});
