/**
 * Copyright 2020 Google LLC
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

import {SelectionModel} from '@angular/cdk/collections';
import {CdkDragDrop, moveItemInArray} from '@angular/cdk/drag-drop';
import {Component, EventEmitter, Input, OnInit, Output, ChangeDetectionStrategy} from '@angular/core';

import {TestRunAction} from '../services/mtt_models';
import {FormChangeTracker} from '../shared/can_deactivate';
import {assertRequiredInput, deepCopy} from '../shared/util';

/**
 * Manages a list of test run actions, allowing users to add, remove, edit, or
 * rearrange them.
 */
@Component({
  changeDetection: ChangeDetectionStrategy.Eager,standalone: false,
  selector: 'test-run-action-picker',
  styleUrls: ['test_run_action_picker.css'],
  templateUrl: './test_run_action_picker.ng.html',
  providers: [{provide: FormChangeTracker, useExisting: TestRunActionPicker}]
})
export class TestRunActionPicker extends FormChangeTracker implements OnInit {
  @Input() actions!: TestRunAction[];
  @Input() selectedActions!: TestRunAction[];
  @Output() readonly selectionChange = new EventEmitter();

  selection = new SelectionModel<TestRunAction>(true, this.selectedActions);

  ngOnInit() {
    assertRequiredInput(this.actions, 'actions', 'test-run-action-picker');
    assertRequiredInput(
        this.selectedActions, 'selectedActions', 'test-run-action-picker');
  }

  /** Moves an action after drag and drop in the selected list. */
  move(event: CdkDragDrop<TestRunAction[]>) {
    moveItemInArray(
        this.selectedActions, event.previousIndex, event.currentIndex);
    this.selectionChange.emit();
  }

  /** Removes an action from the selected list. */
  remove(action: TestRunAction) {
    const index = this.selectedActions.indexOf(action);
    if (index > -1) {
      this.selectedActions.splice(index, 1);
      this.selectionChange.emit();
    }
  }

  /** Adds all actions from the selection menu. */
  addSelected() {
    for (const action of this.selection.selected) {
      this.selectedActions.push(deepCopy(action));
    }
    this.selection.clear();
    this.selectionChange.emit();
  }
}
