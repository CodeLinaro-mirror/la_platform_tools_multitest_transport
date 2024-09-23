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

import {ChangeDetectionStrategy, Component, Input, OnChanges, OnInit, SimpleChanges} from '@angular/core';

import {InvocationStatus} from '../services/tfc_models';
import {TreeNode} from '../shared/tree_table';
import {assertRequiredInput, millisToDuration} from '../shared/util';


/** A component for displaying the module level test run results. */
@Component({
  standalone: false,
  selector: 'test-run-results',
  template: `<tree-table [data]="treeNodes"
                         [columns]="treeTableColumns"></tree-table>`,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TestRunResults implements OnInit, OnChanges {
  @Input() invocationStatus?: InvocationStatus;
  @Input() displayColumns = ['name', 'source', 'link'];

  treeNodes: TreeNode[] = [];
  treeTableColumns = [
    {
      title: 'Name',
      flexWidth: '55',
    },
    {
      title: 'Result',
      flexWidth: '30',
    },
    {
      title: 'Run Time',
      flexWidth: '15',
    },
  ];

  ngOnInit() {
    this.update();
  }

  ngOnChanges(changes: SimpleChanges) {
    this.update();
  }

  private update() {
    this.treeNodes = this.invocationStatus ?
        this.createResultsTree(this.invocationStatus) :
        [];
  }

  /**
   * Returns a Tree Node for displaying invocation results
   *
   * The parent node contains the total test counts and run times of all
   * modules and a list of module nodes as children.
   *
   * If a module has a failure message, that message will be displayed as a
   * child node.
   */
  createResultsTree(invocationStatus: InvocationStatus): TreeNode[] {
    let failedTestCount = 0;
    let passedTestCount = 0;
    let elapsedTime = 0;

    const resultNodes: TreeNode[] = [];
    for (const testGroupStatus of invocationStatus.test_group_statuses || []) {
      // Calculate totals
      failedTestCount += Number(testGroupStatus.failed_test_count || 0);
      passedTestCount += Number(testGroupStatus.passed_test_count || 0);
      elapsedTime += Number(testGroupStatus.elapsed_time || 0);

      // Add message node
      const messageNodes = [];
      if (testGroupStatus.failure_message) {
        messageNodes.push({
          content: [testGroupStatus.failure_message],
          children: [],
          level: 2
        });
      }

      // Add node to array
      resultNodes.push({
        content: [
          testGroupStatus.name,
          this.createTestCountsString(
              testGroupStatus.failed_test_count,
              testGroupStatus.passed_test_count),
          millisToDuration(testGroupStatus.elapsed_time),
        ],
        children: messageNodes,
        level: 1,
      });
    }
    return [{
      content: [
        `Total`, this.createTestCountsString(failedTestCount, passedTestCount),
        millisToDuration(elapsedTime)
      ],
      children: resultNodes,
      level: 0,
      expanded: true,
    }];
  }

  // TODO: Add pass/fail filters

  /** Show PASSED if no failures, FAILED if at least one failure */
  createTestCountsString(failed?: number, passed?: number): string {
    if (typeof failed === 'undefined' || typeof passed === 'undefined') {
      return '';
    }
    if (Number(failed) === 0) {
      return `PASSED (${passed})`;
    }
    return `FAILED (${failed}/${Number(failed) + Number(passed)})`;
  }
}
