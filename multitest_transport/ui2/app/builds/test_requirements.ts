
/**
 * Copyright 2024 Google LLC
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
import {Component, Input} from '@angular/core';
import {MatTableDataSource} from '@angular/material/table';

import {RequiredReport} from '../services/mtt_models';

/**
 * A component for displaying a list of test requirements for a build.
 */
@Component({
  selector: 'test-requirements',
  styleUrls: ['test_requirements.css'],
  templateUrl: './test_requirements.ng.html',
})
export class TestRequirements {
  @Input()
  set dataSource(value: RequiredReport[]) {
    this.tableDataSource.data = value;
  }

  displayColumns =
      ['report_type', 'test_plan', 'test_run', 'test_run_status', 'run_test'];
  tableDataSource = new MatTableDataSource<RequiredReport>();

  get testRunStatus(): string {
    // TODO: Supports test run status.
    return 'NOT_STARTED';
  }
}
