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

import {Component, ElementRef, Input, OnInit, QueryList, ViewChildren, ChangeDetectionStrategy} from '@angular/core';

import {FileCleanerOperation, FileCleanerOperationType} from '../services/mtt_models';
import {FormChangeTracker} from '../shared/can_deactivate';
import {assertRequiredInput} from '../shared/util';

/** Form for file cleaner operation. */
@Component({
  changeDetection: ChangeDetectionStrategy.Eager,standalone: false,
  selector: 'file-cleaner-operation-form',
  styleUrls: ['file_cleaner_operation_form.css'],
  templateUrl: './file_cleaner_operation_form.ng.html',
  providers:
      [{provide: FormChangeTracker, useExisting: FileCleanerOperationForm}],

})
export class FileCleanerOperationForm extends FormChangeTracker implements
    OnInit {
  readonly OPERATION_TYPES = Object.values(FileCleanerOperationType);

  @Input() operation!: FileCleanerOperation;
  @ViewChildren(FormChangeTracker)
  declare trackers: QueryList<FormChangeTracker>;

  ngOnInit() {
    assertRequiredInput(
        this.operation, 'operation', 'file-cleaner-operation-form');
  }

  onAddParam() {
    switch (this.operation.type) {
      case FileCleanerOperationType.ARCHIVE:
        if (this.operation.params!.length >= 1) {
          break;
        }
        this.operation.params!.push({name: 'remove_file', value: 'True'});
        break;
      case FileCleanerOperationType.DELETE:
        break;
      default:
        this.operation.params!.push({name: ''});
    }
  }

  onRemoveParam(i: number) {
    this.operation.params!.splice(i, 1);
  }

  /**
   * Overwrite the FormChangeTracker getInvalidInputs method to allow childs
   * invalidInputs can be propagated to parent page
   */
  override getInvalidInputs(): ElementRef[] {
    this.invalidInputs = super.getInvalidInputs();
    for (const tracker of this.trackers) {
      this.invalidInputs.push(...tracker.getInvalidInputs());
    }
    return this.invalidInputs;
  }
}
