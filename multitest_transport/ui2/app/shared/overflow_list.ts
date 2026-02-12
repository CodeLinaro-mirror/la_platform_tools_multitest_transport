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

import {Component, Input, OnInit, ChangeDetectionStrategy} from '@angular/core';

import {assertRequiredInput} from './util';

/** Type of component to use to display each item */
export enum OverflowListType {
  BUTTON = 'button',
  CHIP = 'chip',
}

/** A component for collapsing and displaying a list of objects. */
@Component({
  changeDetection: ChangeDetectionStrategy.Eager,standalone: false,
  selector: 'overflow-list',
  styleUrls: ['overflow_list.css'],
  templateUrl: './overflow_list.ng.html',
})
export class OverflowList implements OnInit {
  readonly OverflowListType = OverflowListType;

  @Input() data!: string[];
  @Input() overflowListType!: OverflowListType;

  /**
   * Prevent propagation of click event from the dropdown button.
   */
  @Input() preventClickEventPropagation = true;

  ngOnInit() {
    assertRequiredInput(this.data, 'data', 'overflow-list');
    assertRequiredInput(
        this.overflowListType, 'overflowListType', 'overflow-list');
  }

  stopPropagation(event: Event) {
    if (this.preventClickEventPropagation) {
      event.stopPropagation();
    }
  }

  // TODO: Emit clicked items to add filters
}
