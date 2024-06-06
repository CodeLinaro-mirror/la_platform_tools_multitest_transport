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

import {DebugElement} from '@angular/core';
import {ComponentFixture, TestBed} from '@angular/core/testing';
import {NoopAnimationsModule} from '@angular/platform-browser/animations';

import {Test, TestRun} from '../services/mtt_models';
import {getEl} from '../testing/jasmine_util';
import {newMockTest, newMockTestRun} from '../testing/mtt_mocks';

import {TestRunTreeTable} from './test_run_tree_table';
import {TestRunsModule} from './test_runs_module';

describe('TestRunTreeTable', () => {
  let testRunTreeTable: TestRunTreeTable;
  let testRunTreeTableFixture: ComponentFixture<TestRunTreeTable>;
  let el: DebugElement;

  let test: Test;
  let testRun: TestRun;

  beforeEach(() => {
    test = newMockTest();
    testRun = newMockTestRun(test);

    TestBed.configureTestingModule({
      imports: [NoopAnimationsModule, TestRunsModule],
    });

    testRunTreeTableFixture = TestBed.createComponent(TestRunTreeTable);
    testRunTreeTable = testRunTreeTableFixture.componentInstance;
    testRunTreeTable.testRun = testRun;
    testRunTreeTableFixture.detectChanges();
    el = testRunTreeTableFixture.debugElement;
  });

  it('gets initialized', () => {
    expect(testRunTreeTable).toBeTruthy();
  });

  it('displays the correct request values', () => {
    const text = getEl(el, 'mat-tree').textContent;
    expect(text).toContain('test_run');
    expect(text).toContain('total_test_count');
    expect(text).toContain((testRun.total_test_count || -1).toString());
    expect(text).toContain('failed_test_count');
    expect(text).toContain((testRun.failed_test_count || -1).toString());
  });

  it('correctly generates a tree for test run', () => {
    const testRunNode = testRunTreeTable.createTree('test_run', testRun);
    const children = testRunNode.children;
    expect(children[0].content[0]).toContain('id');
    expect(children[0].content[1]).toContain('id123');

    const testNode = children[1];
    expect(testNode.content[0]).toContain('test');
    expect(testNode.children[0].content[0]).toContain('id');
    expect(testNode.children[0].content[1]).toContain('testid123');
  });
});
