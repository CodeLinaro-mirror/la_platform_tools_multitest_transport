/**
 * Copyright 2024 Google LLC
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

import {ComponentFixture, TestBed} from '@angular/core/testing';
import {MatChipInput} from '@angular/material/chips';
import {MAT_DIALOG_DATA, MatDialogRef} from '@angular/material/dialog';
import {NoopAnimationsModule} from '@angular/platform-browser/animations';

import {newMockBuild} from '../testing/mtt_mocks';

import {BuildEditor, BuildEditorData} from './build_editor';
import {BuildsModule} from './builds_module';

describe('BuildEditor', () => {
  const build = newMockBuild(
      'build_id_1', 'name_1', 'file:///file/path_1',
      ['label1', 'label2', 'label3']);
  const dialogData: BuildEditorData = {build};

  let buildEditor: BuildEditor;
  let buildEditorFixture: ComponentFixture<BuildEditor>;
  let dialogRef: jasmine.SpyObj<MatDialogRef<BuildEditor>>;

  beforeEach(() => {
    dialogRef = jasmine.createSpyObj<MatDialogRef<BuildEditor>>(['close']);

    TestBed.configureTestingModule({
      imports: [BuildsModule, NoopAnimationsModule],
      providers: [
        {provide: MAT_DIALOG_DATA, useFactory: () => dialogData},
        {provide: MatDialogRef, useValue: dialogRef},
      ],
    });

    buildEditorFixture = TestBed.createComponent(BuildEditor);
    buildEditorFixture.detectChanges();
    buildEditor = buildEditorFixture.componentInstance;
  });

  it('initializes a component', () => {
    expect(buildEditor).toBeTruthy();
  });

  it('adds labels', () => {
    expect(buildEditor.data.build.labels).toEqual([
      'label1', 'label2', 'label3'
    ]);
    const fakeInput = document.createElement('input');
    buildEditor.addLabel({
      chipInput: {inputElement: fakeInput} as MatChipInput,
      value: ' label4'
    });
    expect(buildEditor.data.build.labels).toEqual([
      'label1', 'label2', 'label3', 'label4'
    ]);

    // Should not add duplicate label
    buildEditor.addLabel({
      chipInput: {inputElement: fakeInput} as MatChipInput,
      value: ' label1  '
    });
    expect(buildEditor.data.build.labels).toEqual([
      'label1', 'label2', 'label3', 'label4'
    ]);
  });

  it('removes labels', () => {
    buildEditor.data.build.labels = ['label1', 'label2'];
    buildEditor.removeLabel('label2');
    expect(buildEditor.data.build.labels).toEqual(['label1']);
    buildEditor.removeLabel('label3');
    expect(buildEditor.data.build.labels).toEqual(['label1']);
    buildEditor.removeLabel('label1');
    expect(buildEditor.data.build.labels).toEqual([]);
    buildEditor.removeLabel('label1');
    expect(buildEditor.data.build.labels).toEqual([]);
  });
});
