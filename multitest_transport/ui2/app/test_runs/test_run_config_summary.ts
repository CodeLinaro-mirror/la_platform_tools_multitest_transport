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
 * A list to display test run config information with create and edit buttons.
 */
@Component({
  selector: 'test-run-config-summary',
  styleUrls: ['test_run_config_summary.css'],
  templateUrl: './test_run_config_summary.ng.html',
})
export class TestRunConfigSummary implements OnInit {
  @Input() config!: mttModels.TestRunConfig;
  @Input() editable = true;
  @Input() title = 'Test Run Config';
  @Output() readonly configChange = new EventEmitter<mttModels.TestRunConfig>();
  @Output() readonly configDelete = new EventEmitter();

  viewDetails = true;
  mttObjectMap = newMttObjectMap();

  constructor(
      private readonly mttObjectMapService: MttObjectMapService,
      private readonly matDialog: MatDialog,
  ) {}

  ngOnInit() {
    assertRequiredInput(this.config, 'test-run-config-summary', 'config');

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

  toggleViewDetails() {
    this.viewDetails = !this.viewDetails;
  }

  editConfig() {
    // Pass in a copy rather than reference to avoid data manipulation
    // on parent component
    const testRunConfigCopy = deepCopy(this.config);
    const testRunConfigEditorData: TestRunConfigEditorData = {
      editMode: true,
      testRunConfig: testRunConfigCopy,
    };

    const dialogRef = this.matDialog.open(TestRunConfigEditor, {
      panelClass: 'test-run-config-editor-dialog',
      data: testRunConfigEditorData,
    });

    dialogRef.componentInstance.configSubmitted.subscribe(
        (result: mttModels.TestRunConfig) => {
          this.configChange.emit(result);
        });
  }

  deleteConfig() {
    this.configDelete.emit();
  }
}
