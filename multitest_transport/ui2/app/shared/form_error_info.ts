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

import {Component, ElementRef, Input, ChangeDetectionStrategy} from '@angular/core';

import {navigateToFirstElement} from './util';

/**
 * An error info message displayed at the bottom of each form if there's error
 * or warning. It also displays a link for user to navigate to the first error.
 */
@Component({
  changeDetection: ChangeDetectionStrategy.Eager,standalone: false,
  selector: 'form-error-info',
  styleUrls: ['form_error_info.css'],
  templateUrl: './form_error_info.ng.html',
})
export class FormErrorInfo {
  @Input() invalidInputs: ElementRef[] = [];
  @Input() errorMessage = '';
  @Input() warningMessage = '';
  navigateToFirstElement = navigateToFirstElement;
}
