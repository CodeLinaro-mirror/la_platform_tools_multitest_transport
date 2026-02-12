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

import {FormChangeTracker} from '../shared/can_deactivate';

import {assertRequiredInput} from './util';

/**
 * Form for managing a list of strings
 */
@Component({
  changeDetection: ChangeDetectionStrategy.Eager,standalone: false,
  selector: 'list-form',
  styleUrls: ['list_form.css'],
  templateUrl: './list_form.ng.html',
  providers: [{provide: FormChangeTracker, useExisting: ListForm}]
})
export class ListForm extends FormChangeTracker implements OnInit {
  @Input() data!: string[];
  @Input() label!: string;
  @Output() readonly addItem = new EventEmitter();
  @Output() readonly removeItem = new EventEmitter<number>();

  ngOnInit() {
    assertRequiredInput(this.data, 'data', 'ListForm');
    assertRequiredInput(this.label, 'label', 'ListForm');
  }

  trackByIdx(index: number, obj: string): number {
    return index;
  }
}
