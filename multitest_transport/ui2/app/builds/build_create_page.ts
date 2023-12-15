/**
 * Copyright 2023 Google LLC
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

import {COMMA, ENTER} from '@angular/cdk/keycodes';
import {AfterViewInit, Component, ViewChild} from '@angular/core';
import {MatButton} from '@angular/material/button';
import {MatChipInputEvent} from '@angular/material/chips';
import {MatDialog} from '@angular/material/dialog';
import {Router} from '@angular/router';

import * as mttModels from '../services/mtt_models';
import {FormChangeTracker} from '../shared/can_deactivate';

/**
 * Component for creating a build.
 */
@Component({
  selector: 'build-create-page',
  styleUrls: ['build_create_page.css'],
  templateUrl: './build_create_page.ng.html',
})
export class BuildCreatePage extends FormChangeTracker implements
    AfterViewInit {
  @ViewChild('backButton', {static: false}) backButton?: MatButton;

  /** Keys used to separate labels */
  readonly separatorKeyCodes: number[] = [ENTER, COMMA];

  data: Partial<mttModels.Build> = mttModels.initBuild();

  constructor(
      private readonly router: Router,
      public dialog: MatDialog,
  ) {
    super();
  }

  ngAfterViewInit() {
    this.backButton!.focus();
  }

  addLabel(event: MatChipInputEvent) {
    const input = event.chipInput.inputElement;
    const value = event.value;

    if ((value || '').trim() &&
        this.data.labels!.indexOf(value.trim()) === -1) {
      this.data.labels!.push(value.trim());
    }

    if (input) {
      input.value = '';
    }
  }

  removeLabel(label: string) {
    const index = this.data.labels!.indexOf(label);
    if (index >= 0) {
      this.data.labels!.splice(index, 1);
    }
  }

  back() {
    this.router.navigate(['builds']);
  }

  // Creates a build.
  submit() {
    // TODO: triggers a request to create a build.
  }
}
