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

import {Component, EventEmitter, Input, OnInit, Output, ChangeDetectionStrategy} from '@angular/core';
import {MatDialog} from '@angular/material/dialog';

import * as mttModels from '../services/mtt_models';
import {MttObjectMapService} from '../services/mtt_object_map';
import {deepCopy} from '../shared/util';

import {TestRunConfigEditor, TestRunConfigEditorData} from './test_run_config_editor';

/**
 * A list to display test run config information with create and edit buttons.
 */
@Component({
  changeDetection: ChangeDetectionStrategy.Eager,standalone: false,
  selector: 'test-run-config-list',
  styleUrls: ['test_run_config_list.css'],
  templateUrl: './test_run_config_list.ng.html',
})
export class TestRunConfigList implements OnInit {
  @Input() data: mttModels.TestRunConfig[] = [];
  @Input() configTemplate?: Partial<mttModels.TestRunConfig>;
  @Input() configTitle = 'Test Run Config';
  @Output() readonly dataChange = new EventEmitter();

  constructor(
      private readonly mttObjectMapService: MttObjectMapService,
      private readonly matDialog: MatDialog,
  ) {}

  ngOnInit() {
    if (!this.configTemplate) {
      this.mttObjectMapService.getMttObjectMap(true /* forceUpdate */)
          .subscribe((res) => {
            this.configTemplate =
                mttModels.initTestRunConfig(Object.values(res.testMap)[0]);
          });
    }
  }

  addConfig() {
    let testRunConfig: Partial<mttModels.TestRunConfig>;
    if (this.data.length === 0) {
      testRunConfig = deepCopy(this.configTemplate!);
    } else {
      testRunConfig = deepCopy(this.data[this.data.length - 1]);
    }
    const testRunConfigEditorData: TestRunConfigEditorData = {
      editMode: false,
      testRunConfig,
    };

    const dialogRef = this.matDialog.open(TestRunConfigEditor, {
      panelClass: 'test-run-config-editor-dialog',
      data: testRunConfigEditorData,
    });

    dialogRef.componentInstance.configSubmitted.subscribe(
        (result: mttModels.TestRunConfig) => {
          this.data.push(result);
          this.dataChange.emit(this.data);
        });
  }

  updateConfig(index: number, config: mttModels.TestRunConfig) {
    this.data[index] = config;
  }

  deleteConfig(index: number) {
    this.data.splice(index, 1);
    this.dataChange.emit(this.data);
  }
}
