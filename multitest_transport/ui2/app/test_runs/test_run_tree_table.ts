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

import {TestRun} from '../services/mtt_models';
import {TreeNode} from '../shared/tree_table';
import {assertRequiredInput} from '../shared/util';

/** A component for displaying the fields of a test run. */
@Component({
  standalone: false,
  selector: 'test-run-tree-table',
  template: `<tree-table [data]="treeNodes"
                         [columns]="treeTableColumns"></tree-table>`,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TestRunTreeTable implements OnInit, OnChanges {
  @Input() testRun!: TestRun;

  treeNodes: TreeNode[] = [];
  treeTableColumns = [
    {
      title: 'Name',
      flexWidth: '30',
    },
    {
      title: 'Value',
      flexWidth: '70',
    },
  ];

  ngOnInit() {
    assertRequiredInput(this.testRun, 'testRun', 'test-run-data-tree');
    this.update();
  }

  ngOnChanges(changes: SimpleChanges) {
    this.update();
  }

  private update() {
    this.treeNodes = this.testRun ?
        [this.createTree('test_run', this.testRun)] :
        [];
  }

  /**
   * Creates a tree node showing all fields of an object
   *
   * @param name The name of the tree node to display
   * @param data The value of the field, displayed as a string or a sub-tree
   * @param level The level of the node in the tree
   * @return the root TreeNode
   */
  createTree(
      name: string,
      data: TestRun|{[key: string]: unknown}|string|number|boolean|Date|undefined,
      level = 0, expanded = true): TreeNode {
    // If no data, return a leaf node
    if (data == null) {
      return {content: [name], children: [], level};
    }

    // If data is a single object, display it
    const leafNodeTypes = ['string', 'number', 'boolean'];
    if (leafNodeTypes.includes(typeof data)) {
      return {content: [name, String(data)], children: [], level};
    }

    // If data is an array or dict, create a sub-tree for it
    const children: TreeNode[] = [];
    for (const [key, value] of Object.entries(data)) {
      children.push(this.createTree(
          key, value as {[key: string]: unknown}, level + 1, false));
    }
    return {
      content: [name],
      children,
      level,
      expanded,
    };
  }
}
