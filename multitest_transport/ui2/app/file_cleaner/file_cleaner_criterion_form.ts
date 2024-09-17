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

import {Component, ElementRef, EventEmitter, Input, OnInit, Output, QueryList, ViewChildren} from '@angular/core';

import {FileCleanerCriterion, FileCleanerCriterionType} from '../services/mtt_models';
import {FormChangeTracker} from '../shared/can_deactivate';
import {assertRequiredInput} from '../shared/util';

/** Form for file cleaner criterion. */
@Component({
  selector: 'file-cleaner-criterion-form',
  styleUrls: ['file_cleaner_criterion_form.css'],
  templateUrl: './file_cleaner_criterion_form.ng.html',
  providers:
      [{provide: FormChangeTracker, useExisting: FileCleanerCriterionForm}],
})
export class FileCleanerCriterionForm extends FormChangeTracker implements
    OnInit {
  readonly CRITERION_TYPES = Object.values(FileCleanerCriterionType);

  @Input() criteria!: FileCleanerCriterion[];
  @Output() readonly addCriterion = new EventEmitter();
  @Output() readonly deleteCriterion = new EventEmitter<number>();

  @ViewChildren(FormChangeTracker)
  declare trackers: QueryList<FormChangeTracker>;

  ngOnInit() {
    assertRequiredInput(
        this.criteria, 'criteria', 'file-cleaner-criterion-form');
  }

  onAddParam(criterion: FileCleanerCriterion) {
    if (criterion.params!.length > 0) {
      return;
    }
    switch (criterion.type) {
      case FileCleanerCriterionType.LAST_ACCESS_TIME:
      case FileCleanerCriterionType.LAST_MODIFIED_TIME:
        criterion.params!.push({name: 'ttl', value: '7 days'});
        break;
      case FileCleanerCriterionType.NAME_MATCH:
        criterion.params!.push({name: 'pattern'});
        break;
      case FileCleanerCriterionType.SYSTEM_AVAILABLE_SPACE:
        criterion.params!.push({name: 'threshold', value: '20GB'});
        break;
      default:
        criterion.params!.push({name: ''});
    }
  }

  onRemoveParam(criterion: FileCleanerCriterion, i: number) {
    criterion.params!.splice(i, 1);
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
