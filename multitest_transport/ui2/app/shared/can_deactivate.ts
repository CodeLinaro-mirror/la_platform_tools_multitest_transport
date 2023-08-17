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

import {Directive, ElementRef, HostListener, Injectable, QueryList, ViewChildren} from '@angular/core';
import {NgModel} from '@angular/forms';
import {MatInput} from '@angular/material/input';
import {MatSelect} from '@angular/material/select';
import {UrlTree} from '@angular/router';
import {Observable} from 'rxjs';

import {Notifier} from '../services/notifier';

/**
 * A class than can track whether a form has dirty input elements.
 * If a page want to trigger UnsavedChangeGuard on navigating away from the
 * page, it has to extend this class.
 */
@Directive()
export abstract class FormChangeTracker {
  /**
   * A form should be consisted of MatInputs, MatSelects and other components
   * that extends FormChangeTracker.
   *
   * For example: setting form has inputs, and name_value_pair_form that
   * collectively make up the form.
   */
  @ViewChildren(MatInput, {read: ElementRef})
  formInputs!: QueryList<ElementRef>;
  @ViewChildren(MatSelect, {read: ElementRef})
  formSelects!: QueryList<ElementRef>;
  @ViewChildren(FormChangeTracker) trackers!: QueryList<FormChangeTracker>;
  // Every formInputs will have a cooresponding ngModel
  @ViewChildren(NgModel) ngmodels!: QueryList<NgModel>;
  /**
   * Form, on submit, will check whether invalid inputs exist
   */
  invalidInputs: ElementRef[] = [];
  /**
   * A boolean which records users actions. (e.g, on press add button,
   * hasContentChanged should be true)
   */
  hasContentChanged = false;

  /**
   * Check whether the form is dirty by examining it's inputs, and recursively
   * examining it's subforms (Component that extends FormChangeTracker).
   */
  isFormDirty(): boolean {
    return this.hasContentChanged ||
        !!this.trackers.find(tracker => tracker.isFormDirty()) ||
        !!this.formInputs.find(
            input => input.nativeElement.classList.contains('ng-dirty'));
  }

  findInvalidFields(): ElementRef[] {
    let invalidFields: ElementRef[] = [];
    // Every control (select, input, textarea) will have ngmodel
    if (!this.ngmodels) {
      return invalidFields;
    }
    // When validating form, touch form fields to show error messages
    for (const ngmodel of this.ngmodels) {
      ngmodel.control.markAsTouched();
    }
    // Find all invalid fields
    invalidFields = this.findInvald(this.formSelects);
    return invalidFields.concat(this.findInvald(this.formInputs));
  }

  private findInvald(list: QueryList<ElementRef>): ElementRef[] {
    return list.filter(
        item => item.nativeElement.classList.contains('ng-invalid'));
  }

  getInvalidInputs(): ElementRef[] {
    this.invalidInputs = this.findInvalidFields();
    return this.invalidInputs;
  }

  /**
   * Reset the form's state to not dirty, it will recursively set the forms
   * input and subforms (Component that extends FormChangeTracker) to clean
   * state
   */
  resetForm() {
    for (const input of this.formInputs) {
      input.nativeElement.classList.remove('ng-dirty');
    }
    for (const tracker of this.trackers) {
      tracker.resetForm();
    }
    this.hasContentChanged = false;
  }

  /**
   * Listen to page close and refresh event, if there's unsaved data,
   * prompt the user to confirm
   * @param $event A beforeUnloadEvent
   */
  @HostListener('window:beforeunload', ['$event'])
  beforeUnload($event: BeforeUnloadEvent) {
    if (this.isFormDirty()) {
      $event.returnValue = '';
    }
  }
}

/**
 * A guard that if added to a route, it will do a check before navigating away
 * form the page. It's used to detect whether the current page has unsaved data.
 * If so, it will prompt user to confirm that they want to navigate away.
 * The component for that route must implement ChangeTracker.
 */
@Injectable()
export class UnsavedChangeGuard {
  constructor(private readonly notifier: Notifier) {}

  canDeactivate(tracker: FormChangeTracker):
      Observable<boolean|UrlTree>|Promise<boolean|UrlTree>|boolean|UrlTree {
    if (tracker.isFormDirty()) {
      return this.notifier.confirm(
          'You have unsaved data. Are you sure you want to navigate away?',
          'Unsaved changes');
    }
    return true;
  }
}
