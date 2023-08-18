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
import {MttObjectMapService, newMttObjectMap} from '../services/mtt_object_map';
import {assertRequiredInput, deepCopy} from '../shared/util';

import {TestRunConfigEditor, TestRunConfigEditorData} from './test_run_config_editor';

/**
 * Displays a list of test run configs that can be editted.
 */
@Component({
  selector: 'test-run-sequence-editor',
  styleUrls: ['test_run_sequence_editor.css'],
  templateUrl: './test_run_sequence_editor.ng.html',
})
export class TestRunSequenceEditor implements OnInit {
  @Input() configList!: mttModels.TestRunConfig[];

  @Input() editable = true;
  @Input() title = 'Test Run Config';
  @Output()
  readonly configListChange = new EventEmitter<mttModels.TestRunConfig[]>();
  @Output() readonly configDelete = new EventEmitter();
  @Output() readonly sequenceDelete = new EventEmitter();

  showRerunConfigs = false;
  mttObjectMap = newMttObjectMap();

  constructor(
      private readonly mttObjectMapService: MttObjectMapService,
      private readonly matDialog: MatDialog,
  ) {}

  ngOnInit() {
    assertRequiredInput(
        this.configList, 'test-run-sequence-editor', 'configList');

    this.mttObjectMapService.getMttObjectMap().subscribe((res) => {
      this.mttObjectMap = res;
    });
  }

  getTestName(id: string) {
    return this.mttObjectMap.testMap[id] ? this.mttObjectMap.testMap[id].name :
                                           `Invalid test: ${id}`;
  }

  getDeviceActionName(id: string) {
    return this.mttObjectMap.deviceActionMap[id] ?
        this.mttObjectMap.deviceActionMap[id].name :
        `Unknown action (${id})`;
  }

  getDeviceActionNameList(actionIds: string[]): string[] {
    if (!actionIds) {
      return [];
    }
    const nameList: string[] = [];
    for (const actionId of actionIds) {
      nameList.push(this.getDeviceActionName(actionId));
    }
    return nameList;
  }

  getTestResourceNameList(resources: mttModels.TestResourceObj[]): string[] {
    if (!resources) {
      return [];
    }
    const nameList: string[] = [];
    for (const resource of resources) {
      nameList.push(resource.name || 'Unknown test resource');
    }
    return nameList;
  }

  getPreview(itemList: string[]) {
    if (itemList.length === 0) {
      return;
    }
    if (itemList.length === 1) {
      return `(${itemList[0]})`;
    }
    return `(${itemList[0]}, ...)`;
  }

  toggleShowRerunConfigs() {
    this.showRerunConfigs = !this.showRerunConfigs;
  }

  editConfig(index: number) {
    // Pass in a copy rather than reference to avoid data manipulation
    // on parent component
    const testRunConfigCopy = deepCopy(this.configList[index]);
    const testRunConfigEditorData: TestRunConfigEditorData = {
      editMode: true,
      testRunConfig: testRunConfigCopy,
    };

    const dialogRef = this.matDialog.open(TestRunConfigEditor, {
      panelClass: 'test-run-config-editor-dialog',
      data: testRunConfigEditorData,
    });

    dialogRef.componentInstance.configSubmitted.subscribe(
        (newConfig: mttModels.TestRunConfig) => {
          this.configList[index] = newConfig;
          this.configListChange.emit(this.configList);
        });
  }

  addRerunConfig() {
    const testRunConfig = deepCopy(this.configList[this.configList.length - 1]);
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
          this.configList.push(newConfig);
          this.configListChange.emit(this.configList);
        });
  }

  deleteConfig() {
    this.configDelete.emit();
  }

  deleteSequence() {
    this.sequenceDelete.emit();
  }
}
