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

import {Component, EventEmitter, Input, OnChanges, OnInit, Output, SimpleChanges, ChangeDetectionStrategy} from '@angular/core';
import {assertRequiredInput} from './util';

/**
 * Breadcrumb component
 */
@Component({
  changeDetection: ChangeDetectionStrategy.Eager,standalone: false,
  selector: 'breadcrumb',
  styleUrls: ['breadcrumb.css'],
  templateUrl: './breadcrumb.ng.html',
})
export class Breadcrumb implements OnChanges, OnInit {
  @Input() prefix?: string;
  @Input() path!: string;
  @Output() readonly pathChange = new EventEmitter<string>();

  pathArray: string[] = [];

  /**
   * Handles changes to component bindings.
   * @param changes Latest changes.
   */
  ngOnChanges(changes: SimpleChanges) {
    if ('path' in changes) {
      this.pathArray = this.path ? this.path.split('/').filter(Boolean) : [];
    }
  }

  ngOnInit() {
    assertRequiredInput(this.path, 'path', 'breadcrumb');
  }

  /**
   * Breadcrumb will render path in form like 'x > y > z', where x, y, z
   * are different clickable paths. This method will be triggered when x, y, z
   * are clicked.
   * @param i The index of the path that is being clicked
   */
  onPathClick(i?: number) {
    if (typeof i === 'undefined') {
      // On click on the root element, clear pathArray
      this.pathArray.length = 0;
    } else {
      // Truncate the path to the correct length
      this.pathArray.length = i + 1;
    }
    this.pathChange.emit(this.pathArray.join('/'));
  }
}
