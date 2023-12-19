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
import {ComponentFixture, TestBed} from '@angular/core/testing';
import {MAT_DIALOG_DATA, MatDialogRef} from '@angular/material/dialog';
import {NoopAnimationsModule} from '@angular/platform-browser/animations';
import {of as observableOf} from 'rxjs';

import {FileService} from '../services/file_service';
import {getTextContent} from '../testing/jasmine_util';

import {BuildFileSelector, BuildFileSelectorData} from './build_file_selector';
import {BuildsModule} from './builds_module';

describe('BuildFileSelector', () => {
  let dialogRef: jasmine.SpyObj<MatDialogRef<BuildFileSelector>>;
  let fs: jasmine.SpyObj<FileService>;

  let fixture: ComponentFixture<BuildFileSelector>;
  let component: BuildFileSelector;
  let el: DebugElement;

  const dialogData: BuildFileSelectorData = {
    fileUrl: '',
  };

  beforeEach(() => {
    fs = jasmine.createSpyObj(['getRelativePathAndHostname', 'listFiles']);
    fs.getRelativePathAndHostname.and.callFake(fileUrl => [fileUrl, '']);
    fs.listFiles.and.returnValue(observableOf([]));
    dialogRef =
        jasmine.createSpyObj<MatDialogRef<BuildFileSelector>>(['close']);

    TestBed.configureTestingModule({
      imports: [BuildsModule, NoopAnimationsModule],
      providers: [
        {provide: FileService, useValue: fs},
        {provide: MAT_DIALOG_DATA, useFactory: () => dialogData},
        {provide: MatDialogRef, useValue: dialogRef},
      ],
    });

    fixture = TestBed.createComponent(BuildFileSelector);
    fixture.detectChanges();
    el = fixture.debugElement;
    component = fixture.componentInstance;
  });

  it('initializes a component', () => {
    expect(component).toBeTruthy();
  });

  it('shows HTML correctly', () => {
    const textContent = getTextContent(el);
    expect(textContent).toContain('Select a file');
  });
});
