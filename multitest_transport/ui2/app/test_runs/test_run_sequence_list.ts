/**
 * Copyright 2021 Google LLC
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

import {Component, EventEmitter, Input, OnInit, Output} from '@angular/core';
import {MatDialog} from '@angular/material/dialog';

import * as mttModels from '../services/mtt_models';
import {MttObjectMapService} from '../services/mtt_object_map';
import {deepCopy} from '../shared/util';

import {TestRunConfigEditor, TestRunConfigEditorData} from './test_run_config_editor';

/**
 * A list to display test run sequence information with create and edit buttons.
 */
@Component({
  selector: 'test-run-sequence-list',
  styleUrls: ['test_run_sequence_list.css'],
  templateUrl: './test_run_sequence_list.ng.html',
})
export class TestRunSequenceList implements OnInit {
  @Input() sequenceList: mttModels.TestRunConfigList[] = [];
  @Input() configTemplate?: Partial<mttModels.TestRunConfig>;
  @Input() configTitle = 'Test Run Config';
  @Output() readonly sequenceListChange = new EventEmitter();

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

  addSequence() {
    let testRunConfig: Partial<mttModels.TestRunConfig>;
    if (this.sequenceList.length === 0) {
      testRunConfig = deepCopy(this.configTemplate!);
    } else {
      testRunConfig = deepCopy(
          this.sequenceList[this.sequenceList.length - 1].test_run_configs[0]);
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
        (newConfig: mttModels.TestRunConfig) => {
          this.sequenceList.push({test_run_configs: [newConfig]});
          this.sequenceListChange.emit(this.sequenceList);
        });
  }

  updateConfigList(
      sequenceIndex: number, configList: mttModels.TestRunConfig[]) {
    this.sequenceList[sequenceIndex].test_run_configs = configList;
    this.sequenceListChange.emit(this.sequenceList);
  }

  deleteConfig(sequenceIndex: number, configIndex: number) {
    this.sequenceList[sequenceIndex].test_run_configs.splice(configIndex, 1);
    this.sequenceListChange.emit(this.sequenceList);
  }

  deleteSequence(sequenceIndex: number) {
    this.sequenceList.splice(sequenceIndex, 1);
    this.sequenceListChange.emit(this.sequenceList);
  }
}
