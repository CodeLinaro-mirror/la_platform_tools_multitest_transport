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

import {SimpleChange} from '@angular/core';
import {ComponentFixture, fakeAsync, TestBed, tick} from '@angular/core/testing';
import {NoopAnimationsModule} from '@angular/platform-browser/animations';
import {RouterTestingModule} from '@angular/router/testing';
import {of, throwError} from 'rxjs';

import {APP_DATA, AppData} from '../services/app_data';
import {FileService} from '../services/file_service';
import {MttClient} from '../services/mtt_client';
import {TestRunOutput} from '../services/mtt_models';
import {CommandAttempt, CommandState} from '../services/tfc_models';
import {newMockRequest, newMockTest, newMockTestRun, newMockTestRunOutput} from '../testing/mtt_mocks';

import {MAX_CONSOLE_LENGTH, POLL_INTERVAL, TestRunConsole} from './test_run_console';
import {TestRunsModule} from './test_runs_module';

/** Constructs an active or inactive command attempt. */
function newCommandAttempt(active: boolean, id = 'attempt_id'): CommandAttempt {
  return {
    request_id: 'request_id',
    command_id: 'command_id',
    attempt_id: id,
    state: active ? CommandState.RUNNING : CommandState.COMPLETED,
    hostname: 'hostname',
  };
}

describe('TestRunConsole', () => {
  let output: TestRunOutput;
  let mtt: jasmine.SpyObj<MttClient>;

  let fixture: ComponentFixture<TestRunConsole>;
  let console: TestRunConsole;
  const appData: AppData = {};

  beforeEach(() => {
    // Set default test run output.
    mtt = jasmine.createSpyObj('mtt', ['getTestRunOutput']);
    output = newMockTestRunOutput(['hello', 'world'], 123);
    mtt.getTestRunOutput.and.returnValue(of(output));

    TestBed.configureTestingModule({
      imports: [TestRunsModule, NoopAnimationsModule, RouterTestingModule],
      providers: [
        {provide: MttClient, useValue: mtt},
        {provide: FileService, useValue: {}},
        {provide: APP_DATA, useValue: appData},
      ],
    });

    // Configure component.
    fixture = TestBed.createComponent(TestRunConsole);
    console = fixture.componentInstance;
    console.testRun = newMockTestRun(newMockTest(), 'test_run_id');
    fixture.detectChanges();

    // Spy on the polling methods.
    spyOn(console, 'clearConsole').and.callThrough();
    spyOn(console, 'resetPolling').and.callThrough();
    spyOn(console, 'stopPolling').and.callThrough();
  });

  afterEach(() => {
    fixture.destroy();
  });

  it('stops polling when disabled', () => {
    console.disabled = true;
    console.ngOnChanges({disabled: new SimpleChange(false, true, true)});
    expect(console.clearConsole).toHaveBeenCalled();
    expect(console.stopPolling).toHaveBeenCalled();
  });

  it('starts polling when enabled', () => {
    const attempt = newCommandAttempt(false);
    console.selectedAttempt = attempt;
    console.request = newMockRequest([], [attempt]);
    console.ngOnChanges({disabled: new SimpleChange(true, false, true)});

    // No changes but will enabling will force polling to restart.
    expect(console.resetPolling).toHaveBeenCalled();
  });

  it('starts polling when request loaded', () => {
    const first = newCommandAttempt(false, 'first');
    const second = newCommandAttempt(false, 'second');

    console.request = newMockRequest([], [first, second]);
    console.ngOnChanges(
        {request: new SimpleChange(undefined, console.request, true)});

    // Selects latest attempt and starts polling.
    expect(console.selectedAttempt).toEqual(second);
    expect(console.clearConsole).toHaveBeenCalled();
    expect(console.resetPolling).toHaveBeenCalled();
  });

  it('can locate selected attempt', () => {
    const active = newCommandAttempt(true, 'valid');
    const final = newCommandAttempt(false, 'valid');
    const other = newCommandAttempt(false, 'invalid');

    console.selectedAttempt = active;
    console.request = newMockRequest([], [final, other]);
    console.ngOnChanges(
        {request: new SimpleChange(undefined, console.request, true)});

    // Finds the right attempt without restarting polling.
    expect(console.selectedAttempt).toEqual(final);
    expect(console.clearConsole).not.toHaveBeenCalled();
    expect(console.resetPolling).not.toHaveBeenCalled();
  });

  it('cannot load without attempt', () => {
    console.selectedAttempt = undefined;
    console.resetPolling();

    expect(mtt.getTestRunOutput).not.toHaveBeenCalled();
    expect(console.output).toEqual([]);
    expect(console.offset).toBeUndefined();
  });

  it('can load active console', fakeAsync(() => {
       console.selectedAttempt = newCommandAttempt(true);
       console.resetPolling();

       expect(mtt.getTestRunOutput)
           .toHaveBeenCalledWith(
               'test_run_id', 'attempt_id', 'logs/host_log.txt', undefined);
       expect(console.output).toEqual(['world']);  // First line skipped.
       expect(console.offset).toEqual(output.offset + output.length - 1);

       tick(POLL_INTERVAL);
       expect(console.output).toEqual(['world', 'world']);  // Auto-updates.

       console.stopPolling();
     }));

  it('can load inactive console', fakeAsync(() => {
       console.selectedAttempt = newCommandAttempt(false);
       console.resetPolling();

       expect(mtt.getTestRunOutput)
           .toHaveBeenCalledWith(
               'test_run_id', 'attempt_id', 'tool-logs/host_log.txt',
               undefined);
       expect(console.output).toEqual(['world']);  // First line skipped.
       expect(console.offset).toEqual(output.offset + output.length - 1);

       tick(POLL_INTERVAL);
       expect(console.output).toEqual(['world']);  // Doesn't auto-update.

       console.stopPolling();
     }));

  it('can change log type', () => {
    console.selectedAttempt = newCommandAttempt(false);
    console.selectedType = 'stdout.txt';
    console.resetPolling();

    expect(mtt.getTestRunOutput)
        .toHaveBeenCalledWith(
            'test_run_id', 'attempt_id', 'tool-logs/stdout.txt', undefined);
  });

  it('can handle errors', fakeAsync(() => {
       // 2nd request will fail
       mtt.getTestRunOutput.and.returnValues(
           of(output), throwError('expected'), of(output));
       console.selectedAttempt = newCommandAttempt(true);
       console.resetPolling();

       tick(POLL_INTERVAL);
       expect(console.output).toEqual([]);      // Output cleared.
       expect(console.offset).toBeUndefined();  // Offset reset.

       tick(POLL_INTERVAL);
       expect(console.output).toEqual(['world']);  // Continues to auto-update.

       console.stopPolling();
     }));

  it('can truncate console', () => {
    // Fetch twice as much content as the maximum.
    const length = 2 * MAX_CONSOLE_LENGTH;
    const content = Array.from<string>({length}).fill('test');
    mtt.getTestRunOutput.and.returnValue(of(newMockTestRunOutput(content)));

    console.selectedAttempt = newCommandAttempt(false);
    console.resetPolling();

    // Content was truncated.
    expect(console.output.length).toEqual(MAX_CONSOLE_LENGTH);
  });

  it('can restart polling', fakeAsync(() => {
       console.selectedAttempt = newCommandAttempt(true);
       console.resetPolling();
       expect(mtt.getTestRunOutput).toHaveBeenCalledTimes(1);

       // Delay not reached, but restarting the polling will fetch data.
       tick(POLL_INTERVAL / 2);
       expect(mtt.getTestRunOutput).toHaveBeenCalledTimes(1);
       console.resetPolling();
       expect(mtt.getTestRunOutput).toHaveBeenCalledTimes(2);

       // Poll delay has been reset.
       tick(POLL_INTERVAL / 2);
       expect(mtt.getTestRunOutput).toHaveBeenCalledTimes(2);
       tick(POLL_INTERVAL / 2);
       expect(mtt.getTestRunOutput).toHaveBeenCalledTimes(3);

       console.stopPolling();
     }));
});
