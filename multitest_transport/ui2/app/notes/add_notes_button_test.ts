/**
 * Copyright 2020 Google LLC
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
import {MatDialog} from '@angular/material/dialog';
import {NoopAnimationsModule} from '@angular/platform-browser/animations';

import {NoteDialogState, NotesDialog} from '../notes/notes_dialog';

import {AddNotesButton} from './add_notes_button';
import {NotesModule} from './notes_module';

describe('AddNotesButton', () => {
  let addNotesButton: AddNotesButton;
  let addNotesButtonFixture: ComponentFixture<AddNotesButton>;
  let el: DebugElement;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [
        NotesModule,
        NoopAnimationsModule,
      ],
    });

    addNotesButtonFixture = TestBed.createComponent(AddNotesButton);
    el = addNotesButtonFixture.debugElement;
    addNotesButton = addNotesButtonFixture.componentInstance;
    addNotesButtonFixture.detectChanges();
  });

  it('initializes a component', () => {
    expect(addNotesButton).toBeTruthy();
  });

  it('opens note editor dialog correctly', async () => {
    const dialog = TestBed.inject(MatDialog);
    spyOn(dialog, 'open').and.callThrough();
    spyOn(addNotesButton, 'notesUpdated');

    const mockClickEvent = new MouseEvent('click');
    const ids = ['device1', 'device2'];
    const lab = 'lab-1';
    const deviceHostMap: Array<[string, string]> =
        [['device1', 'host1'], ['device10', 'host5']];

    const dialogParams = {
      height: '600px',
      width: '1200px',
      data: {
        dialogState: NoteDialogState.EDITOR,
        noteType: addNotesButton.noteType,
        ids,
        deviceHostMap,
        labName: lab,
      },
      autoFocus: false,
    };

    addNotesButton.ids = ids;
    addNotesButton.labName = lab;
    addNotesButton.deviceHostMap = deviceHostMap;

    // Trigger open editor dialog.
    addNotesButton.openNoteCreateEditor(mockClickEvent);
    expect(dialog.open).toHaveBeenCalledWith(NotesDialog, dialogParams);
  });
});
