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

import {Component, Input, OnChanges, OnInit, SimpleChanges, ChangeDetectionStrategy} from '@angular/core';
import {assertRequiredInput} from '../shared/util';

/**
 * A component for displaying status.
 */
@Component({
  changeDetection: ChangeDetectionStrategy.Eager,standalone: false,
  selector: 'status-button',
  styleUrls: ['status_button.css'],
  templateUrl: './status_button.ng.html',
})
export class StatusButton implements OnInit, OnChanges {
  @Input() state!: string;

  ngOnInit() {
    assertRequiredInput(this.state, 'state', 'status-button');
  }

  ngOnChanges(changes: SimpleChanges) {
    this.state = this.state.replace('_', ' ');
  }
}
