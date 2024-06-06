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
import {FileCleanerSettings} from '../services/mtt_models';
import {Notifier} from '../services/notifier';
import {getEl, getEls, getTextContent} from '../testing/jasmine_util';
import {newMockFileCleanerConfig, newMockFileCleanerPolicy} from '../testing/mtt_mocks';

import {FileCleanerConfigEditPage} from './file_cleaner_config_edit_page';
import {FileCleanerModule} from './file_cleaner_module';

describe('FileCleanerConfigEditPage', () => {
  let notifier: jasmine.SpyObj<Notifier>;
  let client: jasmine.SpyObj<MttClient>;

  let fixture: ComponentFixture<FileCleanerConfigEditPage>;
  let element: DebugElement;
  let component: FileCleanerConfigEditPage;

  beforeEach(() => {
    notifier = jasmine.createSpyObj(['showError']);
    client = jasmine.createSpyObj(['getFileCleanerSettings']);
    client.getFileCleanerSettings.and.returnValue(
        observableOf({configs: [newMockFileCleanerConfig()]}));

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

    fixture = TestBed.createComponent(FileCleanerConfigEditPage);
    fixture.detectChanges();
    element = fixture.debugElement;
    component = fixture.componentInstance;
  });

  /** Convenience method to reload new file cleaner config. */
  function reload(settings: FileCleanerSettings, index: number = 0) {
    client.getFileCleanerSettings.and.returnValue(observableOf(settings));
    component.load(index);
    fixture.detectChanges();
  }

  it('can initialize the component', () => {
    expect(component).toBeTruthy();
  });

  it('can call API correctly', () => {
    expect(client.getFileCleanerSettings).toHaveBeenCalled();
  });

  it('can display texts correctly', () => {
    const textContent = getTextContent(element);
    expect(textContent).toContain('Edit file cleaner config');
    expect(textContent).toContain('Config Information');
    expect(textContent).toContain('Directories');
    expect(textContent).toContain('Policy Names');
    expect(textContent).toContain('No file cleaner policy found.');
  });

  it('can filter invalid policy names', () => {
    reload({
      policies: [newMockFileCleanerPolicy('Policy #1')],
      configs: [newMockFileCleanerConfig(
          'Config', '', [], ['Policy #1', 'Policy #2'])],
    });

    expect(component.data.policy_names!.length).toBe(1);
    expect(component.data.policy_names![0]).toBe('Policy #1');
  });

  it('can handle errors when loading settings', () => {
    client.getFileCleanerSettings.and.returnValue(throwError('loading failed'));
    component.load(0);
    expect(notifier.showError).toHaveBeenCalled();
  });

  it('can handle directory list form event', () => {
    expect(component.data.directories).toBeDefined();
    component.onAddDirectory();
    component.onAddDirectory();
    expect(component.data.directories!.length).toBe(2);

    const first = component.data.directories![0];
    component.onDeleteDirectory(1);
    expect(component.data.directories!.length).toBe(1);
    expect(component.data.directories![0]).toBe(first);
  });

  it('can add policy name', () => {
    reload({policies: [newMockFileCleanerPolicy('Policy')]});

    getEl(element, '.add-policy-button').click();
    fixture.detectChanges();

    expect(getEls(element, 'mat-select').length).toBe(1);
    expect(component.data.policy_names!.length).toBe(1);
  });

  it('can delete policy name', () => {
    reload({
      policies: [
        newMockFileCleanerPolicy('Policy #1'),
        newMockFileCleanerPolicy('Policy #2'),
      ],
      configs: [newMockFileCleanerConfig(
          'Config', '', [], ['Policy #1', 'Policy #2'])],
    });

    getEls(element, '.delete-policy-button')[0].click();
    fixture.detectChanges();

    expect(getEls(element, 'mat-select').length).toBe(1);
    expect(component.data.policy_names!.length).toBe(1);
    expect(component.data.policy_names![0]).toBe('Policy #2');
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
