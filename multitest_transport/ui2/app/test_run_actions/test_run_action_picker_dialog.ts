/**
 * Copyright 2022 Google LLC
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
import {Component, EventEmitter, Inject, Output, ChangeDetectionStrategy} from '@angular/core';
import {MAT_DIALOG_DATA, MatDialogRef} from '@angular/material/dialog';

import {TestRunAction, TestRunActionRef} from '../services/mtt_models';
import {Notifier} from '../services/notifier';
import {deepCopy} from '../shared/util';

/**
 * Data format when passed to TestRunActionPickerDialog
 * @param actions avaliable test run actions
 * @param selectedActionRefs references for selected actions
 */
export interface TestRunActionPickerDialogData {
  actions: TestRunAction[];
  selectedActionRefs: TestRunActionRef[];
}

/**
 * The dialog component to select test run actions .
 */
@Component({
  changeDetection: ChangeDetectionStrategy.Eager,standalone: false,
  selector: 'test-run-action-picker-dialog',
  styleUrls: ['test_run_action_picker_dialog.css'],
  templateUrl: './test_run_action_picker_dialog.ng.html',
})
export class TestRunActionPickerDialog {
  @Output() readonly confirm = new EventEmitter<TestRunActionRef[]>();

  selectedActions: TestRunAction[] = [];

  constructor(
      private readonly notifier: Notifier,
      public dialogRef: MatDialogRef<TestRunActionPickerDialog>,
      @Inject(MAT_DIALOG_DATA) public data:
          TestRunActionPickerDialogData,
  ) {
    const actionMap: {[id: string]: TestRunAction} = {};
    for (const action of data.actions) {
      actionMap[action.id] = action;
    }
    for (const ref of data.selectedActionRefs) {
      if (actionMap[ref.action_id]) {
        const selectedAction = deepCopy(actionMap[ref.action_id]);
        selectedAction.options = ref.options;
        this.selectedActions.push(selectedAction);
      }
    }
  }

  execute() {
    this.notifier
        .confirm('Do you want to execute these test run actions?', 'Confirm')
        .subscribe(result => {
          if (!result) {
            return;
          }
          this.confirm.emit(this.selectedActions.map(
              action => ({action_id: action.id, options: action.options})));
          this.dialogRef.close();
        });
  }
}