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

import {Component, DebugElement} from '@angular/core';
import {ComponentFixture, TestBed} from '@angular/core/testing';
import {NoopAnimationsModule} from '@angular/platform-browser/animations';

import {getEl, hasEl} from '../testing/jasmine_util';

import {SharedModule} from './shared_module';

describe('ForbiddenValuesValidator', () => {
  let fixture: ComponentFixture<TestComponent>;
  let element: DebugElement;
  let component: TestComponent;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [NoopAnimationsModule, SharedModule],
      declarations: [TestComponent],
    });

    fixture = TestBed.createComponent(TestComponent);
    fixture.detectChanges();
    element = fixture.debugElement;
    component = fixture.componentInstance;
  });

  it('can initialize the component', () => {
    expect(component).toBeTruthy();
  });

  it('can be valid when the value is not forbidden', () => {
    const input: HTMLInputElement = getEl(element, 'input');
    input.value = 'value';
    input.dispatchEvent(new Event('input'));
    input.dispatchEvent(new Event('blur'));
    fixture.detectChanges();

    expect(hasEl(element, 'mat-error')).toBeFalsy();
  });

  it('can be invalid when the value is forbidden', () => {
    const input: HTMLInputElement = getEl(element, 'input');
    input.value = 'forbidden';
    input.dispatchEvent(new Event('input'));
    input.dispatchEvent(new Event('blur'));
    fixture.detectChanges();

    expect(hasEl(element, 'mat-error')).toBeTruthy();
    expect(getEl(element, 'mat-error').textContent)
        .toContain('Value is forbidden');
  });
});

@Component({
  standalone: false,
  template: `<mat-form-field>
               <input matInput mttForbiddenValues [forbiddenValues]="values"
                      [(ngModel)]="data.value" #value="ngModel" />
                 <mat-error *ngIf="value.invalid && value.errors?.forbidden">
                    Value is forbidden
                 </mat-error>
             </mat-form-field>`,
// TODO: Make this AOT compatible. See b/352713444
jit: true,

})
class TestComponent {
  values = new Set<string>(['forbidden']);
  data = {'value': ''};
}
