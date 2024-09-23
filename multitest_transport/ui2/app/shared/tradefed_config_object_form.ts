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

import {Component, ElementRef, EventEmitter, Input, OnInit, Output, QueryList, ViewChildren} from '@angular/core';

import {TradefedConfigObject} from '../services/mtt_models';
import {FormChangeTracker} from '../shared/can_deactivate';

import {OptionValueChangeEvent} from './name_multi_value_pair_list_form';
import {assertRequiredInput} from './util';

/**
 * Form for Tradefed Config Object
 */
@Component({
  standalone: false,
  selector: 'tradefed-config-object-form',
  styleUrls: ['tradefed_config_object_form.css'],
  templateUrl: './tradefed_config_object_form.ng.html',
  providers:
      [{provide: FormChangeTracker, useExisting: TradefedConfigObjectForm}]
})
export class TradefedConfigObjectForm extends FormChangeTracker implements
    OnInit {
  @Input() configObjects!: Array<Partial<TradefedConfigObject>>;
  @Input() configObjectName = 'Config Object';
  @Input() canEdit = true;
  @Output() readonly addConfigObject = new EventEmitter();
  @Output() readonly deleteConfigObject = new EventEmitter<number>();
  @ViewChildren(FormChangeTracker)
  declare trackers: QueryList<FormChangeTracker>;

  ngOnInit() {
    assertRequiredInput(
        this.configObjects, 'configObjects', 'tradefed-config-object-form');
  }

  /** Add an option to config object */
  onAddOption(configObject: Partial<TradefedConfigObject>) {
    if (!configObject) {
      return;
    }
    if (!configObject.option_values) {
      configObject.option_values = [];
    }
    configObject.option_values.push({name: '', values: []});
  }

  /** Remove the ith option from config object */
  onRemoveOption(configObject: Partial<TradefedConfigObject>, i: number) {
    if (!configObject || !configObject.option_values ||
        !configObject.option_values[i]) {
      return;
    }
    configObject.option_values.splice(i, 1);
  }

  /** On option value change, convert the value from string to list */
  onOptionValueChange(
      configObject: Partial<TradefedConfigObject>,
      event: OptionValueChangeEvent) {
    const arr = event.value.split('\n');
    if (!configObject || !configObject.option_values ||
        !configObject.option_values[event.index]) {
      return;
    }
    configObject.option_values[event.index].values = arr;
    return arr;
  }

  /**
   * Overwrite the FormChangeTracker getInvalidInputs method
   * to allow childs invalidInputs can be propagated to parent
   * page
   */
  override getInvalidInputs(): ElementRef[] {
    this.invalidInputs = super.getInvalidInputs();
    for (const tracker of this.trackers) {
      this.invalidInputs.push(...tracker.getInvalidInputs());
    }
    return this.invalidInputs;
  }
}
