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
import {MatTableDataSource} from '@angular/material/table';

import {FileService} from '../services/file_service';
import {TestResourceObj, TestRun} from '../services/mtt_models';
import {assertRequiredInput} from '../shared/util';


/** A component for displaying the console output from a test run. */
@Component({
  standalone: false,
  selector: 'test-resource-list',
  templateUrl: './test_resource_list.ng.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TestResourceList implements OnInit, OnChanges {
  @Input() testRun!: TestRun;
  @Input() displayColumns = ['name', 'source', 'link'];

  dataSource = new MatTableDataSource<TestResourceObj>([]);

  constructor(private readonly fs: FileService) {}

  ngOnInit() {
    assertRequiredInput(this.testRun, 'testRun', 'test-run-resources');
    this.update();
  }

  ngOnChanges(changes: SimpleChanges) {
    this.update();
  }

  private update() {
    this.dataSource.data = this.testRun && this.testRun.test_resources || [];
  }

  getTestResourceLink(cacheUrl: string) {
    return this.fs.getFileOpenUrl(cacheUrl);
  }
}
