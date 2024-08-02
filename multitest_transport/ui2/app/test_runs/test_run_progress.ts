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

import {KeyValue} from '@angular/common';
import {Component, Input, OnChanges, OnInit, SimpleChanges} from '@angular/core';
import * as moment from 'moment';
import {finalize} from 'rxjs/operators';

import {FileService} from '../services/file_service';
import {EventLogEntry, EventLogLevel, TestRun} from '../services/mtt_models';
import {TfcClient} from '../services/tfc_client';
import {Command, CommandAttempt, CommandState, CommandStateStats, isFinalCommandState, Request} from '../services/tfc_models';
import {assertRequiredInput, millisToDuration} from '../shared/util';

/** Progress entity which represents a log entry. */
interface LogEntity extends EventLogEntry {
  readonly progressType: 'log';
  readonly timestamp: moment.Moment;
}

/** Progress entity which represents command state stats. */
interface CommandStateStatsEntity extends CommandStateStats {
  readonly progressType: 'command-state-stats';
  readonly timestamp: moment.Moment;
}

/** Progress entity which represents an attempt. */
interface AttemptEntity extends CommandAttempt {
  readonly progressType: 'attempt';
  readonly timestamp: moment.Moment;
}

/** Entities which define a test run's progress. */
type ProgressEntity = LogEntity|AttemptEntity|CommandStateStatsEntity;

/** Tree node for storing command data */
interface CommandNode extends Command {
  attemptNodeMap: {[attemptId: string]: CommandAttemptNode};
  expanded: boolean;
}

/** Tree node for storing attempt data */
interface CommandAttemptNode extends CommandAttempt {
  expanded: boolean;
}

/** Tree node for storing state stats data. */
interface CommandStateStatNode {
  state: CommandState;
  count: number;
  commandNodeMap: {[commandId: string]: CommandNode};
  expanded: boolean;
  pageToken?: string;
  isLoading: boolean;
}

/** Displays the test run progress entities (log entries and attempts). */
@Component({
  selector: 'test-run-progress',
  styleUrls: ['test_run_progress.css'],
  templateUrl: './test_run_progress.ng.html',
})
export class TestRunProgress implements OnInit, OnChanges {
  readonly EventLogLevel = EventLogLevel;
  readonly CommandState = CommandState;

  @Input() testRun!: TestRun;
  @Input() request?: Request;

  entities: ProgressEntity[] = [];
  stateStats: CommandStateStats = {state_stats: []};
  statNodeMap: {[state in CommandState]?: CommandStateStatNode} = {};

  displayColumns = [
    'expand',
    'jobs',
    'module_results',
    'test_results',
    'start_time',
    'duration',
    'output_files',
  ];

  constructor(
      private readonly fs: FileService,
      private readonly tfcClient: TfcClient,
  ) {}

  ngOnInit() {
    assertRequiredInput(this.testRun, 'testRun', 'test-run-progress');
  }

  ngOnChanges(changes: SimpleChanges) {
    if (changes['testRun'] || changes['request']) {
      this.loadCommandStateStats();
    }
  }

  loadCommandStateStats() {
    if (!this.request) {
      this.updateEntities();
      return;
    }
    this.tfcClient.getCommandStateStats(this.request.id)
        .pipe(finalize(() => {
          this.updateEntities();
        }))
        .subscribe(
            (res) => {
              this.stateStats = res;

              for (const stat of this.stateStats.state_stats) {
                if (stat.count !== 0) {
                  this.statNodeMap[stat.state] = {
                    state: stat.state,
                    count: stat.count,
                    commandNodeMap: {},
                    expanded: false,
                    isLoading: false,
                  };
                }
              }
            },
            error => {
              console.log('Failed to load command state stats: %s', error);
            });
  }

  updateEntities() {
    // Convert log entries
    const logEntries = this.testRun.log_entries || [];
    const logEntities: LogEntity[] = logEntries.map(e => {
      return {progressType: 'log', timestamp: moment.utc(e.create_time), ...e};
    });

    // Convert command states
    const stateStatsEntity: CommandStateStatsEntity = {
      progressType: 'command-state-stats',
      timestamp: moment.utc(this.stateStats.create_time) || moment.now(),
      ...this.stateStats,
    };

    // Convert attempts
    const commands = this.request && this.request.commands || [];
    const commandMap = commands.reduce((map: Map<string, Command>, obj: Command) => {
      map.set(obj.id, obj);
      return map;
    }, new Map<string, Command>());
    const attempts = this.request && this.request.command_attempts || [];
    const attemptEntities: AttemptEntity[] = attempts.map(e => {
      return {
        progressType: 'attempt',
        timestamp: moment.utc(e.create_time),
        command: commandMap.get(e.command_id),
        ...e,
      };
    });

    // Combine and sort entities
    this.entities = [...logEntities, ...attemptEntities, stateStatsEntity].sort(
        (a, b) => a.timestamp.diff(b.timestamp));
  }

  expandStatNode(state: CommandState) {
    if (!this.statNodeMap[state]) {
      return;
    }
    if (this.statNodeMap[state]!.expanded) {
      this.statNodeMap[state]!.expanded = false;
      return;
    }
    this.statNodeMap[state]!.expanded = true;
    this.loadCommands(state);
  }

  expandCommandNode(state: CommandState, commandId: string) {
    if (!this.statNodeMap[state] ||
        !this.statNodeMap[state]!.commandNodeMap[commandId]) {
      return;
    }
    if (this.statNodeMap[state]!.commandNodeMap[commandId].expanded) {
      this.statNodeMap[state]!.commandNodeMap[commandId].expanded = false;
      return;
    }
    this.statNodeMap[state]!.commandNodeMap[commandId].expanded = true;
    this.loadAttempts(state, commandId);
  }

  expandAttemptNode(state: CommandState, commandId: string, attemptId: string) {
    if (!this.statNodeMap[state] ||
        !this.statNodeMap[state]!.commandNodeMap[commandId] ||
        !this.statNodeMap[state]!.commandNodeMap[commandId]
             .attemptNodeMap[attemptId]) {
      return;
    }
    this.statNodeMap[state]!.commandNodeMap[commandId]
        .attemptNodeMap[attemptId]
        .expanded = !this.statNodeMap[state]!.commandNodeMap[commandId]
                         .attemptNodeMap[attemptId]
                         .expanded;
  }

  loadCommands(state: CommandState) {
    if (!this.request) {
      return;
    }
    if (!this.statNodeMap[state]) {
      console.log(
          'Attempting to load commands for state not in state map: %s', state);
      return;
    }

    this.tfcClient.listCommands(this.request.id, state)
        .pipe()
        .subscribe(
            res => {
              const commandNodeMap: {[commandId: string]: CommandNode} = {};
              for (const command of res.commands) {
                commandNodeMap[command.id] = Object.assign(command, {
                  attemptNodeMap: {},
                  expanded: false,
                });
              }
              this.statNodeMap[state]!.commandNodeMap = commandNodeMap;
              this.statNodeMap[state]!.pageToken = res.page_token;
            },
            error => {
              // TODO: Convert to notifier dialogs
              console.log(
                  'Failed to load commands for state %s: %s', state, error);
            });
  }

  loadMoreCommands(state: CommandState) {
    if (!this.request) {
      return;
    }
    if (!this.statNodeMap[state]) {
      console.log(
          'Attempting to load commands for state not in state map: %s', state);
      return;
    }

    this.statNodeMap[state]!.isLoading = true;
    this.tfcClient
        .listCommands(
            this.request.id, state, this.statNodeMap[state]!.pageToken)
        .pipe(finalize(() => {
          this.statNodeMap[state]!.isLoading = false;
        }))
        .subscribe(
            res => {
              for (const command of res.commands) {
                this.statNodeMap[state]!.commandNodeMap[command.id] =
                    Object.assign(command, {
                      attemptNodeMap: {},
                      expanded: false,
                    });
              }
              this.statNodeMap[state]!.pageToken = res.page_token;
            },
            error => {
              // TODO: Convert to notifier dialogs
              console.log(
                  'Failed to load commands for state %s: %s', state, error);
            });
  }

  loadAttempts(state: CommandState, commandId: string) {
    if (!this.request) {
      return;
    }
    if (!this.statNodeMap[state]) {
      console.log(
          'Attempting to load commands for state not in state map: %s', state);
      return;
    }
    if (!this.statNodeMap[state]!.commandNodeMap[commandId]) {
      console.log(
          'Attempting to load attempts for command not in command map: %s',
          commandId);
      return;
    }

    this.tfcClient.listCommandAttempts(this.request.id, commandId)
        .pipe()
        .subscribe(
            res => {
              const attemptNodeMap:
                  {[attemptId: string]: CommandAttemptNode} = {};
              for (const attempt of res.command_attempts) {
                attemptNodeMap[attempt.attempt_id] = Object.assign(attempt, {
                  expanded: false,
                });
              }
              this.statNodeMap[state]!.commandNodeMap[commandId]
                  .attemptNodeMap = attemptNodeMap;
            },
            error => {
              // TODO: Convert to notifier dialogs
              console.log(
                  'Failed to load attempts for command %s: %s', commandId,
                  error);
            });
  }

  getAttemptExtraInfo(attempt: CommandAttemptNode): string|undefined {
    switch (attempt.state) {
      case CommandState.COMPLETED:
        return attempt.summary;
      case CommandState.ERROR:
      case CommandState.FATAL:
        return attempt.subprocess_command_error || attempt.error;
      default:
        return undefined;
    }
  }

  getAttemptExtraInfoLines(attempt: CommandAttemptNode): string[] {
    const s = this.getAttemptExtraInfo(attempt);
    if (!s) {
      return [];
    }
    return s.trim().split('\n');
  }

  isFinished(attempt: CommandAttempt): boolean {
    return isFinalCommandState(attempt.state);
  }

  /** Generate the output files URL for an attempt. */
  getOutputFilesUrl(attempt: CommandAttempt): string {
    const url = this.fs.getTestRunFileUrl(this.testRun, attempt);
    return this.fs.getFileBrowseUrl(url);
  }

  /**
   * Iterates using insertion order when using keyvalue for a map.
   *
   * The default iteration behavior for keyvalue is to sort by key, but this
   * causes the list to look jumbled when loading new entries since we load by
   * create_time.
   **/
  originalOrder = (a: KeyValue<number, string>, b: KeyValue<number, string>):
      number => {
        return 0;
      }

  /** Calculate an attempt's duration. */
  getDuration(attempt: CommandAttempt): string {
    const start = moment.utc(attempt.start_time);
    const end =
        this.isFinished(attempt) ? moment.utc(attempt.end_time) : moment.utc();
    return millisToDuration(end.diff(start));
  }
}
