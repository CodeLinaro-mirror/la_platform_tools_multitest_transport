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

import {Component, ElementRef, Inject, Input, OnChanges, OnDestroy, OnInit, SimpleChanges, ViewChild} from '@angular/core';
import {defer, EMPTY, iif, of, ReplaySubject, Subscription, timer} from 'rxjs';
import {catchError, filter, repeat, switchMapTo, take, takeUntil} from 'rxjs/operators';

import {APP_DATA, AppData} from '../services/app_data';
import {FileService} from '../services/file_service';
import {MttClient} from '../services/mtt_client';
import {TestRun} from '../services/mtt_models';
import {CommandAttempt, isFinalCommandState, Request} from '../services/tfc_models';
import {assertRequiredInput} from '../shared/util';

/** Log directory when attempt is active. */
export const ACTIVE_LOG_DIR = 'logs/';
/** Log directory when attempt is complete. */
export const FINAL_LOG_DIR = 'tool-logs/';
/** Log types and filenames. */
export const LOG_TYPES = {
  'Host Log': 'host_log.txt',
  'Test Log': 'stdout.txt',
};
/** Omnilab log types and filenames. */
export const OMNILAB_LOG_TYPES = {
  'Host Log': 'test_output.txt',
  'Test Log': 'xts_tf_output.log',
};
/** Maximum lines to keep. */
export const MAX_CONSOLE_LENGTH = 200;
/** Auto-update polling interval (ms). */
export const POLL_INTERVAL = 4_000;

/** A component for displaying the console output from a test run. */
@Component({
  selector: 'test-run-console',
  styleUrls: ['test_run_console.css'],
  templateUrl: './test_run_console.ng.html',
})
export class TestRunConsole implements OnInit, OnChanges, OnDestroy {
  /** True to disable the console auto-updating. */
  @Input() disabled = false;
  @Input() testRun!: TestRun;
  @Input() request?: Request;

  invocations?: CommandAttempt[];
  selectedAttempt?: CommandAttempt;
  LOG_TYPES = LOG_TYPES;
  selectedType = Object.values(LOG_TYPES)[0];
  /** True if current logs have been fetched at least once. */
  initialized = false;
  offset?: number;
  output: string[] = [];

  /** Notified when the component is destroyed. */
  private readonly destroy = new ReplaySubject<void>();
  /** Periodically polls for new content. */
  private polling: Subscription|null = null;

  @ViewChild('outputContainer', {static: false}) outputContainer!: ElementRef;

  constructor(
      @Inject(APP_DATA) private readonly appData: AppData,
      private readonly fs: FileService, private readonly mtt: MttClient) {
    if (this.appData.isOmniLabBased) {
      this.LOG_TYPES = OMNILAB_LOG_TYPES;
      this.selectedType = Object.values(this.LOG_TYPES)[0];
    }
  }

  ngOnInit() {
    assertRequiredInput(this.testRun, 'testRun', 'test-run-console');
    this.update();
  }

  ngOnDestroy() {
    this.destroy.next();
  }

  ngOnChanges(changes: SimpleChanges) {
    this.update(!!changes['disabled']);
  }

  /** Update parameters and polling. */
  private update(force = false) {
    this.invocations = this.request && this.request.command_attempts || [];

    // Check if disabled or nothing to display.
    if (this.disabled || !this.invocations) {
      this.clearConsole();
      this.stopPolling();
      return;
    }

    // Try to find previously selected attempt.
    const attemptId = this.selectedAttempt && this.selectedAttempt.attempt_id;
    this.selectedAttempt =
        this.invocations.find(attempt => attempt.attempt_id === attemptId);
    if (!this.selectedAttempt) {
      // Previous attempt not found - default to last one.
      this.selectedAttempt = this.invocations[this.invocations.length - 1];
      this.clearConsole();
      this.resetPolling();
    } else if (force) {
      // Otherwise, only restart polling if forced.
      this.resetPolling();
    }
  }

  /** @return path to the selected attempt's log. */
  getLogPath(): string|null {
    if (!this.selectedAttempt) {
      return null;
    }
    const isActive = !isFinalCommandState(this.selectedAttempt.state);
    if (this.appData.isOmniLabBased) {
      return 'tradefed_logs/XtsTradefedTest_test_' +
          `${this.selectedAttempt.attempt_id}/${this.selectedType}`;
    }
    return (isActive ? ACTIVE_LOG_DIR : FINAL_LOG_DIR) + this.selectedType;
  }

  /** @return URL to view selected attempt's log. */
  getLogUrl(): string|null {
    const path = this.getLogPath();
    if (!path || !this.selectedAttempt) {
      return null;
    }
    const url =
        this.fs.getTestRunFileUrl(this.testRun, this.selectedAttempt, path);
    return this.fs.getFileOpenUrl(url);
  }

  /** Clear console output. */
  clearConsole() {
    this.output = [];
    this.offset = undefined;
  }

  /** Stop and restart polling. */
  resetPolling() {
    this.stopPolling();
    this.startPolling();
  }

  /** Stop polling if currently active. */
  stopPolling() {
    if (this.polling) {
      this.polling.unsubscribe();
    }
  }

  /** Determines whether polling should continue, i.e. attempt is active. */
  private shouldPoll(): boolean {
    const attempt = this.selectedAttempt;
    return !!attempt && !isFinalCommandState(attempt.state);
  }

  /** Starts periodically fetching the console. */
  private startPolling() {
    this.initialized = false;
    const update = timer(POLL_INTERVAL).pipe(filter(() => this.shouldPoll()));

    this.polling =
        // Always fetch at least once, but only auto-update if active.
        iif(() => !this.initialized, of(true), update)
            .pipe(take(1))
            .pipe(switchMapTo(defer(() => {
              const attempt = this.selectedAttempt;
              const path = this.getLogPath();
              if (!this.testRun.id || this.disabled || !attempt || !path) {
                this.initialized = true;
                return EMPTY;
              }

              return this.mtt.getTestRunOutput(
                  this.testRun.id, attempt.attempt_id, path, this.offset);
            })))
            .pipe(catchError(() => {
              // Failed to fetch content.
              this.clearConsole();
              this.initialized = true;
              return EMPTY;
            }))
            // Repeat indefinitely until unsubscribed or destroyed.
            .pipe(repeat())
            .pipe(takeUntil(this.destroy))
            .subscribe(output => {
              if (this.isAtBottom()) {
                // Scroll to bottom after component view updated
                setTimeout(() => {
                  this.scrollToBottom();
                });
              }

              // Load the new output lines
              const lines = output.lines ? output.lines.slice(1) : [];
              if (lines.length >= MAX_CONSOLE_LENGTH) {
                // Too many new lines, clear console and show only new lines
                this.output = lines.slice(-MAX_CONSOLE_LENGTH);
              } else {
                // Add new lines and trim older lines
                this.output =
                    this.output.concat(lines).slice(-MAX_CONSOLE_LENGTH);
              }

              this.offset = Number(output.offset) + Number(output.length) - 1;
              this.initialized = true;
            });
  }


  private isAtBottom(): boolean {
    const element = this.outputContainer.nativeElement;
    return element.scrollTop === element.scrollHeight - element.clientHeight;
  }

  private scrollToBottom() {
    this.outputContainer.nativeElement.scrollTop =
        this.outputContainer.nativeElement.scrollHeight;
  }
}
