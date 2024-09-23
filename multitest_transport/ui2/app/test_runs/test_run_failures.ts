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

import {Component, Input, OnChanges, OnInit, SimpleChanges} from '@angular/core';
import {isFinalTestRunState, TestRunState} from '../services/mtt_models';
import {assertRequiredInput} from '../shared/util';
/**
 * Type of display to show
 * If PASSED or FAILED, color and an icon will also be added
 *
 * Passed: Completed with 0 failures
 * Failed: Error or completed with some failures
 * Neutral: No tests run (usually when canceled)
 * Pending: Test run not completed yet (pending, queued, or running)
 */
export enum DisplayMode {
  PENDING = 'PENDING',
  NEUTRAL = 'NEUTRAL',
  PASSED = 'PASSED',
  FAILED = 'FAILED',
}

/**
 * A component for displaying a test run results (tests failed / tests run).
 */
@Component({
  standalone: false,
  selector: 'test-run-failures',
  styleUrls: ['test_run_failures.css'],
  templateUrl: './test_run_failures.ng.html',
})
export class TestRunFailures implements OnInit, OnChanges {
  @Input() state!: TestRunState;
  @Input() numFailedTests = 0;
  @Input() numTotalTests = 0;
  @Input() numFailedModules = 0;
  readonly DisplayMode = DisplayMode;
  displayMode = DisplayMode.PENDING;

  ngOnInit() {
    assertRequiredInput(this.state, 'state', 'TestRunStatus');
  }

  ngOnChanges(changes: SimpleChanges): void {
    this.numFailedTests = Number(this.numFailedTests || 0);
    this.numTotalTests = Number(this.numTotalTests || 0);
    this.numFailedModules = Number(this.numFailedModules || 0);
    this.updateDisplayMode();
  }

  /**
   * Sets display mode to:
   * PASSED if state is COMPLETED and no tests failed
   * FAILED if state is ERROR or some tests failed
   * NEUTRAL if state is final and no tests were run (usually if CANCELED)
   * PENDING if state is not final
   */
  updateDisplayMode() {
    if ((this.state === TestRunState.COMPLETED) &&
        (this.numFailedTests === 0)) {
      this.displayMode = DisplayMode.PASSED;
    } else if (
        (this.state === TestRunState.ERROR) || (this.numFailedTests > 0)) {
      this.displayMode = DisplayMode.FAILED;
    } else if (isFinalTestRunState(this.state)) {
      this.displayMode = DisplayMode.NEUTRAL;
    } else {
      this.displayMode = DisplayMode.PENDING;
    }
  }
}
