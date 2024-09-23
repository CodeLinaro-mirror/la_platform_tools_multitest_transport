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

import {NestedTreeControl} from '@angular/cdk/tree';
import {ChangeDetectionStrategy, Component, Input, OnChanges, OnInit, SimpleChanges} from '@angular/core';
import {MatTreeNestedDataSource} from '@angular/material/tree';

import {assertRequiredInput} from './util';

/** A tree node structure */
export interface TreeNode {
  content: string[];
  children: TreeNode[];
  level: number;
  expanded?: boolean;
}

/** Column of a tree table */
export interface TreeTableColumn {
  title: string;     /** String to display in the header of the table */
  flexWidth: string; /** Flex width percentage */
}

/** A component for displaying a tree structure as a table. */
@Component({
  standalone: false,
  selector: 'tree-table',
  styleUrls: ['tree_table.css'],
  templateUrl: './tree_table.ng.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TreeTable implements OnInit, OnChanges {
  @Input() data!: TreeNode[];
  @Input() columns!: TreeTableColumn[];

  treeControl = new NestedTreeControl<TreeNode>(node => node.children);
  dataSource = new MatTreeNestedDataSource<TreeNode>();
  columnNames: string[] = [];

  ngOnInit() {
    assertRequiredInput(this.data, 'data', 'tree-table');
    assertRequiredInput(this.columns, 'columns', 'tree-table');
    this.update(this.data || []);
    this.columnNames = this.columns.map(column => column.title);
  }

  ngOnChanges(changes: SimpleChanges) {
    if (changes['data']) {
      this.update(this.data || []);
    }
  }

  private update(nodes: TreeNode[]) {
    this.dataSource.data = nodes;
    this.treeControl.dataNodes = nodes;
    this.expand(nodes);
  }

  private expand(nodes: TreeNode[]) {
    for (const node of nodes) {
      if (node.expanded) {
        this.treeControl.expand(node);
        this.expand(node.children);
      }
    }
  }

  hasChild = (index: number, node: TreeNode) =>
      !!node.children && node.children.length > 0;
}
