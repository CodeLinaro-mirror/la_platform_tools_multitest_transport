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

import {DebugElement} from '@angular/core';
import {ComponentFixture, inject, TestBed} from '@angular/core/testing';
import {MatChipInput} from '@angular/material/chips';
import {MatDialog} from '@angular/material/dialog';
import {NoopAnimationsModule} from '@angular/platform-browser/animations';
import {Router} from '@angular/router';
import {RouterTestingModule} from '@angular/router/testing';
import {of as observableOf} from 'rxjs';

import {BuildClient, MttClient} from '../services/mtt_client';
import {getEl} from '../testing/jasmine_util';
import {newMockBuild} from '../testing/mtt_mocks';

import {BuildCreatePage} from './build_create_page';
import {BuildsModule} from './builds_module';

describe('BuildCreatePage', () => {
  let buildCreatePage: BuildCreatePage;
  let buildCreatePageFixture: ComponentFixture<BuildCreatePage>;
  let buildClient: jasmine.SpyObj<BuildClient>;

  let el: DebugElement;

  beforeEach(() => {
    buildClient = jasmine.createSpyObj('buildClient', ['create']);
    buildClient.create.and.returnValue(observableOf(newMockBuild(
        'build_id_1', 'name_1', 'file:///file/path_1',
        ['label_1', 'label_2'])));

    TestBed.configureTestingModule({
      imports: [BuildsModule, NoopAnimationsModule, RouterTestingModule],
      providers: [
        {provide: MttClient, useValue: {builds: buildClient}},
      ],
    });

    buildCreatePageFixture = TestBed.createComponent(BuildCreatePage);
    buildCreatePageFixture.detectChanges();
    el = buildCreatePageFixture.debugElement;
    buildCreatePage = buildCreatePageFixture.componentInstance;
  });

  it('initializes a component', () => {
    expect(buildCreatePage).toBeTruthy();
  });

  it('adds labels', () => {
    expect(buildCreatePage.data.labels).toEqual([]);
    const fakeInput = document.createElement('input');
    buildCreatePage.addLabel({
      chipInput: {inputElement: fakeInput} as MatChipInput,
      value: ' label1  '
    });
    expect(buildCreatePage.data.labels).toEqual(['label1']);
    buildCreatePage.addLabel({
      chipInput: {inputElement: fakeInput} as MatChipInput,
      value: 'label2'
    });
    expect(buildCreatePage.data.labels).toEqual(['label1', 'label2']);

    // Should not add duplicate label
    buildCreatePage.addLabel({
      chipInput: {inputElement: fakeInput} as MatChipInput,
      value: ' label1  '
    });
    expect(buildCreatePage.data.labels).toEqual(['label1', 'label2']);
  });

  it('removes labels', () => {
    buildCreatePage.data.labels = ['label1', 'label2', 'label3'];
    buildCreatePage.removeLabel('label2');
    expect(buildCreatePage.data.labels).toEqual(['label1', 'label3']);
    buildCreatePage.removeLabel('label3');
    expect(buildCreatePage.data.labels).toEqual(['label1']);
    buildCreatePage.removeLabel('label4');
    expect(buildCreatePage.data.labels).toEqual(['label1']);
    buildCreatePage.removeLabel('label1');
    expect(buildCreatePage.data.labels).toEqual([]);
    buildCreatePage.removeLabel('label1');
    expect(buildCreatePage.data.labels).toEqual([]);
  });

  describe('back button', () => {
    it('should display correct aria-label and tooltip', () => {
      const backButton = getEl(el, '#back-button');
      expect(backButton).toBeTruthy();
      expect(backButton.getAttribute('aria-label'))
          .toBe('Return to builds page');
      expect(backButton.getAttribute('mattooltip'))
          .toBe('Return to builds page');
    });
  });

  describe('create button', () => {
    it('should display correct aria-label', () => {
      const createButton = getEl(el, '.create-button');
      expect(createButton).toBeTruthy();
      expect(createButton.getAttribute('aria-label')).toBe('Create');
    });
  });

  describe('cancel button', () => {
    it('should display correct aria-label', () => {
      const cancelButton = getEl(el, '.cancel-button');
      expect(cancelButton).toBeTruthy();
      expect(cancelButton.getAttribute('aria-label')).toBe('Cancel');
    });
  });

  it('should open build file seletor dialog when clicking source form field',
     () => {
       let dialogSpy: jasmine.Spy;
       const dialogRefSpy =
           jasmine.createSpyObj({afterClosed: observableOf(''), close: null});
       dialogSpy = spyOn(TestBed.inject(MatDialog), 'open')
                       .and.returnValue(dialogRefSpy);
       getEl(el, '.source-field').click();
       expect(dialogSpy).toHaveBeenCalled();
       expect(dialogRefSpy.afterClosed).toHaveBeenCalled();
     });

  it('creates new build', inject([Router], (router: Router) => {
       spyOn(router, 'navigate');
       getEl(el, '.create-button').click();
       expect(buildClient.create).toHaveBeenCalled();
       expect(router.navigate).toHaveBeenCalledWith([`builds/build_id_1`]);
     }));
});
