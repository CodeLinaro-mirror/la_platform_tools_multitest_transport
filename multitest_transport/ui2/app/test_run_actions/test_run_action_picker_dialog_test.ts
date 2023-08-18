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

import {DebugElement} from '@angular/core';
import {ComponentFixture, TestBed} from '@angular/core/testing';
import {MAT_DIALOG_DATA, MatDialogRef} from '@angular/material/dialog';
import {NoopAnimationsModule} from '@angular/platform-browser/animations';
import {of as observableOf} from 'rxjs';

import {Notifier} from '../services/notifier';
import {getEl, getEls} from '../testing/jasmine_util';

import {TestRunActionPickerDialog} from './test_run_action_picker_dialog';
import {TestRunActionsModule} from './test_run_actions_module';

describe('TestRunActionPickerDialog', () => {
  let dialogRefSpy:
      jasmine.SpyObj<MatDialogRef<TestRunActionPickerDialog>>;
  let notifier: jasmine.SpyObj<Notifier>;

  let fixture: ComponentFixture<TestRunActionPickerDialog>;
  let element: DebugElement;
  let component: TestRunActionPickerDialog;

  beforeEach(() => {
    dialogRefSpy = jasmine.createSpyObj(['close']);
    notifier = jasmine.createSpyObj(['confirm']);

    TestBed.configureTestingModule({
      imports: [NoopAnimationsModule, TestRunActionsModule],
      providers: [
        {
          provide: MAT_DIALOG_DATA,
          useFactory: () => ({
            actions: [
              {
                id: 'id',
                name: 'name',
                hook_class_name: 'hook',
                options: [{name: 'option', value: 'value'}],
              },
            ],
            selectedActionRefs: [
              {
                action_id: 'id',
                options: [{name: 'option', value: 'new value'}],
              },
              {action_id: 'unknown id', options: []},
            ],
          })
        },
        {provide: MatDialogRef, useValue: dialogRefSpy},
        {provide: Notifier, useValue: notifier},
      ],
    });

    fixture = TestBed.createComponent(TestRunActionPickerDialog);
    element = fixture.debugElement;
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('can initialize the component', () => {
    expect(component).toBeTruthy();
  });

  it('can display the intersection of actions and selected action refs', () => {
    const items = getEls(element, '.test-run-action-item');
    expect(items.length).toBe(1);
  });

  it('can return the selected action refs when confirm', () => {
    notifier.confirm.and.returnValue(observableOf(true));
    spyOn(component.confirm, 'emit');

    getEl(element, '.execute-button').click();

    expect(notifier.confirm).toHaveBeenCalled();
    expect(component.confirm.emit).toHaveBeenCalledWith([{
      action_id: 'id',
      options: [{name: 'option', value: 'new value'}],
    }]);
    expect(dialogRefSpy.close).toHaveBeenCalled();
  });
});
