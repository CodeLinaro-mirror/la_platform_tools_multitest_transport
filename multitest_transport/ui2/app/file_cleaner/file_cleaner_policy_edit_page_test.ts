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

import {DebugElement} from '@angular/core';
import {ComponentFixture, TestBed} from '@angular/core/testing';
import {NoopAnimationsModule} from '@angular/platform-browser/animations';
import {ActivatedRoute, RouterModule} from '@angular/router';
import {of as observableOf, throwError} from 'rxjs';

import {MttClient} from '../services/mtt_client';
import {Notifier} from '../services/notifier';
import {getEl, getTextContent} from '../testing/jasmine_util';
import {newMockFileCleanerPolicy} from '../testing/mtt_mocks';

import {FileCleanerModule} from './file_cleaner_module';
import {FileCleanerPolicyEditPage} from './file_cleaner_policy_edit_page';

describe('FileCleanerPolicyEditPage', () => {
  let notifier: jasmine.SpyObj<Notifier>;
  let client: jasmine.SpyObj<MttClient>;

  let fixture: ComponentFixture<FileCleanerPolicyEditPage>;
  let element: DebugElement;
  let component: FileCleanerPolicyEditPage;

  beforeEach(() => {
    notifier = jasmine.createSpyObj(['showError']);
    client = jasmine.createSpyObj(['getFileCleanerSettings']);
    client.getFileCleanerSettings.and.returnValue(
        observableOf({policies: [newMockFileCleanerPolicy()]}));

    TestBed.configureTestingModule({
      imports: [FileCleanerModule, NoopAnimationsModule, RouterModule],
      providers: [
        {
          provide: ActivatedRoute,
          useValue: {
            params: observableOf({'index': '0'}),
          },
        },
        {provide: Notifier, useValue: notifier},
        {provide: MttClient, useValue: client},
      ]
    });

    fixture = TestBed.createComponent(FileCleanerPolicyEditPage);
    fixture.detectChanges();
    element = fixture.debugElement;
    component = fixture.componentInstance;
  });

  it('can initialize the component', () => {
    expect(component).toBeTruthy();
  });

  it('can call API correctly', () => {
    expect(client.getFileCleanerSettings).toHaveBeenCalled();
  });

  it('can display texts correctly', () => {
    const textContent = getTextContent(element);
    expect(textContent).toContain('Edit file cleaner policy');
    expect(textContent).toContain('Policy Information');
    expect(textContent).toContain('Name');
    expect(textContent).toContain('Target Type');
    expect(textContent).toContain('File Cleaner Operation');
    expect(textContent).toContain('File Cleaner Criteria');
  });

  it('can handle errors when loading settings', () => {
    client.getFileCleanerSettings.and.returnValue(throwError('loading failed'));
    component.load(0);
    expect(notifier.showError).toHaveBeenCalled();
  });

  it('can handle criterion form event', () => {
    expect(component.data.criteria).toBeDefined();
    component.onAddCriterion();
    component.onAddCriterion();
    expect(component.data.criteria!.length).toBe(2);

    const first = component.data.criteria![0];
    component.onDeleteCriterion(1);
    expect(component.data.criteria!.length).toBe(1);
    expect(component.data.criteria![0]).toBe(first);
  });

  describe('back button', () => {
    it('should display correct aria-label and tooltip', () => {
      const backButton = getEl(element, '#back-button');
      expect(backButton).toBeTruthy();
      expect(backButton.getAttribute('aria-label'))
          .toBe('Return to settings page');
      expect(backButton.getAttribute('mattooltip'))
          .toBe('Return to settings page');
    });
  });
});
