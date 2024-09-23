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

import {Component, Input, OnInit} from '@angular/core';

import {FileService} from '../services/file_service';
import {TestRun} from '../services/mtt_models';
import {CommandAttempt, CommandState, isFinalCommandState} from '../services/tfc_models';
import {assertRequiredInput} from '../shared/util';


/** A component for displaying a test job status info. */
@Component({
  standalone: false,
  selector: 'attempt-status',
  styleUrls: ['attempt_status.css'],
  templateUrl: './attempt_status.ng.html',
})
export class AttemptStatus implements OnInit {
  commandState = CommandState;

  @Input() testRun!: TestRun;
  @Input() attempt!: CommandAttempt;

  showExtraInfo = false;

  constructor(private readonly fs: FileService) {}

  ngOnInit() {
    assertRequiredInput(this.testRun, 'testRun', 'attempt-status');
    assertRequiredInput(this.attempt, 'attempt', 'attempt-status');
  }

  getCalloutType() {
    switch(this.attempt.state) {
      case CommandState.QUEUED:
      case CommandState.RUNNING:
        return 'inprogress';
      case CommandState.COMPLETED:
        if (this.attempt.failed_test_run_count &&
            this.attempt.failed_test_run_count > 0) {
          return 'warning';
        }
        return 'success';
      case CommandState.ERROR:
      case CommandState.FATAL:
        return 'error';
      case CommandState.CANCELED:
        return 'info';
      default:
        return 'warning';
    }
  }

  getExtraInfo(): string | undefined {
    switch(this.attempt.state) {
      case CommandState.COMPLETED:
        return this.attempt.summary;
      case CommandState.ERROR:
      case CommandState.FATAL:
        return this.attempt.subprocess_command_error || this.attempt.error;
      default:
        return undefined;
    }
  }

  getExtraInfoLines(): string[] {
    const s = this.getExtraInfo();
    if (!s) {
      return [];
    }
    return s.trim().split('\n');
  }

  isFinished(): boolean {
    return isFinalCommandState(this.attempt.state);
  }

  /** Generate the output files URL for an attempt. */
  getOutputFilesUrl(): string {
    const url = this.fs.getTestRunFileUrl(this.testRun, this.attempt);
    return this.fs.getFileBrowseUrl(url);
  }

  getExecutedTestCount(): number {
    return Number(this.attempt.failed_test_count) +
        Number(this.attempt.passed_test_count);
  }
}
