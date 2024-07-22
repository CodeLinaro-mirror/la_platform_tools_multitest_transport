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

import {Component, DebugElement} from '@angular/core';
import {ComponentFixture, TestBed} from '@angular/core/testing';
import {NoopAnimationsModule} from '@angular/platform-browser/animations';
import {Observable, of as observableOf} from 'rxjs';

import {Notifier} from '../services/notifier';

import {FormChangeTracker, UnsavedChangeGuard} from './can_deactivate';
import {SharedModule} from './shared_module';

class FalseTracker extends FormChangeTracker {
  override isFormDirty() {
    return false;
  }
}

class TrueTracker extends FormChangeTracker {
  override isFormDirty() {
    return true;
  }
}

describe('UnsavedChangeGuard', () => {
  let guard: UnsavedChangeGuard;
  let notifier: jasmine.SpyObj<Notifier>;
  beforeEach(() => {
    notifier = jasmine.createSpyObj('notifier', ['confirm']);
  });

  it('behaves correctly when component is not dirty', () => {
    notifier.confirm.and.returnValue(observableOf(true));
    guard = new UnsavedChangeGuard(notifier);
    const mockFalseComponent = new FalseTracker();
    expect(guard.canDeactivate(mockFalseComponent)).toBe(true);
  });

  it('behaves correctly when component is dirty and user confirmed', () => {
    notifier.confirm.and.returnValue(observableOf(true));
    guard = new UnsavedChangeGuard(notifier);
    const mockTrueComponent = new TrueTracker();
    (guard.canDeactivate(mockTrueComponent) as Observable<boolean>)
        .subscribe(result => {
          expect(result).toBe(true);
        });
  });

  it('behaves correctly when component is dirty and user did not confirm',
     () => {
       notifier.confirm.and.returnValue(observableOf(false));
       guard = new UnsavedChangeGuard(notifier);
       const mockTrueComponent = new TrueTracker();
       (guard.canDeactivate(mockTrueComponent) as Observable<boolean>)
           .subscribe(result => {
             expect(result).toBe(false);
           });
     });
});

@Component({
  selector: 'test-component-child',
  providers: [{provide: FormChangeTracker, useExisting: TestComponentChild}],
  template: `
      <div>
        <input matInput type="text" [(ngModel)]="value" name="value">
      </div>`,
// TODO: Make this AOT compatible. See b/352713444
jit: true,

})
class TestComponentChild extends FormChangeTracker {
  value = '123';
}

@Component({
  template: `
      <div>
        <input matInput type="text" [(ngModel)]="value" name="value">
        <test-component-child></test-component-child>
      </div>`,
// TODO: Make this AOT compatible. See b/352713444
jit: true,

})
class TestComponent extends FormChangeTracker {
  value = '123';
}


describe('FormChangeTracker', () => {
  let testComponent: TestComponent;
  let testComponentFixture: ComponentFixture<TestComponent>;
  let el: DebugElement;
  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [NoopAnimationsModule, SharedModule],
      declarations: [TestComponent, TestComponentChild],
      });
    testComponentFixture = TestBed.createComponent(TestComponent);
    testComponent = testComponentFixture.componentInstance;
    el = testComponentFixture.debugElement;
    testComponentFixture.detectChanges();
  });

  it('initializes a component', () => {
    expect(testComponent).toBeTruthy();
  });

  it('has correct number of inputs', () => {
    expect(testComponent.formInputs.length).toBe(1);
  });

  it('has correct number of components that are changeTrackers', async () => {
    await testComponentFixture.whenStable();
    expect(testComponent.trackers.length).toBe(1);
  });

  describe('isFormDirty', () => {
    it('bahaves correctly on clean form', () => {
      expect(testComponent.isFormDirty()).toBe(false);
      testComponent.formInputs.first.nativeElement.classList.add('ng-dirty');
      expect(testComponent.isFormDirty()).toBe(true);
    });
  });

  describe('resetForm', () => {
    it('remove the ng-dirty field from input', () => {
      expect(testComponent.isFormDirty()).toBe(false);
      testComponent.formInputs.first.nativeElement.classList.add('ng-dirty');
      testComponent.resetForm();
      expect(testComponent.isFormDirty()).toBe(false);
    });
  });
});
