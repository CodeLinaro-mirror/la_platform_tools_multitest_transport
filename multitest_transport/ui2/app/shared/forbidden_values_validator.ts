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

import {Directive, Input} from '@angular/core';
import {AbstractControl, NG_VALIDATORS, ValidationErrors, Validator} from '@angular/forms';

/** A directive that checks whether the control value is forbidden. */
@Directive({
  standalone: false,
  selector: '[mttForbiddenValues]',
  providers: [
    {provide: NG_VALIDATORS, useExisting: ForbiddenValuesValidator, multi: true}
  ]
})
export class ForbiddenValuesValidator implements Validator {
  @Input('forbiddenValues') forbiddenValues = new Set<string>();

  validate(control: AbstractControl): ValidationErrors|null {
    return this.forbiddenValues.has(control.value) ?
        {forbidden: {value: control.value}} :
        null;
  }
}
