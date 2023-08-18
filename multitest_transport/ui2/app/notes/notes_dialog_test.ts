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

import {HttpClientTestingModule} from '@angular/common/http/testing';
import {ComponentFixture, TestBed} from '@angular/core/testing';
import {MAT_DIALOG_DATA, MatDialogRef} from '@angular/material/dialog';
import {NoopAnimationsModule} from '@angular/platform-browser/animations';
import {ActivatedRoute, Router} from '@angular/router';
import {APP_DATA, Notifier} from 'google3/third_party/py/multitest_transport/ui2/app/services';
import {of as observableOf} from 'rxjs';

import {NoteType} from '../services/mtt_lab_models';
import {ActivatedRouteStub} from '../testing/activated_route_stub';
import {newMockAppData} from '../testing/mtt_lab_mocks';

import {NoteDialogState, NotesDialog} from './notes_dialog';
import {NotesModule} from './notes_module';

describe('NotesDialog', () => {
  const serial1 = 'serial1';
  const serial2 = 'serial2';
  const noteId = 201;
  const labName = 'lab 1';
  let dialogRefSpy: jasmine.SpyObj<MatDialogRef<NotesDialog>>;
  let routerSpy: jasmine.SpyObj<Router>;
  let notesDialog: NotesDialog;
  let notesDialogFixture: ComponentFixture<NotesDialog>;
  let notifier: jasmine.SpyObj<Notifier>;

  const noteDialogParams = {
    dialogState: NoteDialogState.LIST,
    noteType: NoteType.DEVICE,
    ids: ['serial'],
    noteId: 0,
    labName,
  };

  beforeEach(() => {
    const activatedRouteSpy = new ActivatedRouteStub({});
    routerSpy = jasmine.createSpyObj('Router', ['navigateByUrl', 'navigate']);
    dialogRefSpy = jasmine.createSpyObj<MatDialogRef<NotesDialog>>(
        'dialogRefSpy', ['close']);
    notifier = jasmine.createSpyObj('notifier', ['showError']);

    TestBed.configureTestingModule({
      imports: [
        NoopAnimationsModule,
        NotesModule,
        HttpClientTestingModule,
      ],
      providers: [
        {provide: MAT_DIALOG_DATA, useValue: noteDialogParams},
        {provide: APP_DATA, useValue: newMockAppData()},
        {provide: MatDialogRef, useValue: dialogRefSpy},
        {provide: Notifier, useValue: notifier},
        {provide: Router, useValue: routerSpy},
        {provide: ActivatedRoute, useValue: activatedRouteSpy},
      ],
    });

    notesDialogFixture = TestBed.createComponent(NotesDialog);
    notesDialog = notesDialogFixture.componentInstance;
    notesDialog.id = serial1;
    notesDialogFixture.detectChanges();
  });

  it('initializes a component', () => {
    expect(notesDialog).toBeTruthy();
  });

  it('returns true when dialogState=LIST with a id', () => {
    expect(notesDialog.validateParams(noteDialogParams)).toEqual(true);
  });

  it('returns false when dialogState=LIST with a id and a noteId', () => {
    noteDialogParams.noteId = noteId;
    expect(notesDialog.validateParams(noteDialogParams)).toEqual(false);
  });

  it('returns false when dialogState=LIST without id', () => {
    noteDialogParams.ids = [];
    noteDialogParams.labName = labName;
    expect(notesDialog.validateParams(noteDialogParams)).toEqual(false);
  });

  it('returns false when dialogState=LIST with multiple ids', () => {
    noteDialogParams.ids = [serial1, serial2];
    notesDialog.id = serial1;
    expect(notesDialog.validateParams(noteDialogParams)).toEqual(false);
  });

  it('returns false when dialogState=LIST with a noteId', () => {
    noteDialogParams.ids = [];
    noteDialogParams.noteId = noteId;
    expect(notesDialog.validateParams(noteDialogParams)).toEqual(false);
  });

  it('returns true when dialogState=EDITOR with an id', () => {
    // Add note to a device/host
    noteDialogParams.dialogState = NoteDialogState.EDITOR;
    noteDialogParams.ids = [serial1];
    noteDialogParams.noteId = 0;
    expect(notesDialog.validateParams(noteDialogParams)).toEqual(true);
  });

  it('returns true when dialogState=EDITOR with multiple ids', () => {
    // Add note to multiple devices/hosts
    noteDialogParams.dialogState = NoteDialogState.EDITOR;
    noteDialogParams.ids = [serial1, serial2];
    noteDialogParams.noteId = 0;
    expect(notesDialog.validateParams(noteDialogParams)).toEqual(true);
  });

  it('returns false when dialogState=EDITOR without id and noteId', () => {
    noteDialogParams.dialogState = NoteDialogState.EDITOR;
    noteDialogParams.ids = [];
    noteDialogParams.noteId = 0;
    expect(notesDialog.validateParams(noteDialogParams)).toEqual(false);
  });

  it('returns true when dialogState=EDITOR with a noteId and an id', () => {
    // Edit the note
    noteDialogParams.dialogState = NoteDialogState.EDITOR;
    noteDialogParams.ids = [serial1];
    noteDialogParams.noteId = noteId;
    expect(notesDialog.validateParams(noteDialogParams)).toEqual(true);
  });

  it('returns false when dialogState=EDITOR with a noteId without id', () => {
    noteDialogParams.dialogState = NoteDialogState.EDITOR;
    noteDialogParams.ids = [];
    noteDialogParams.noteId = noteId;
    expect(notesDialog.validateParams(noteDialogParams)).toEqual(false);
  });

  it('returns false when dialogState=EDITOR with a noteId with multiple ids',
     () => {
       noteDialogParams.dialogState = NoteDialogState.EDITOR;
       noteDialogParams.ids = [serial1, serial2];
       noteDialogParams.noteId = noteId;
       expect(notesDialog.validateParams(noteDialogParams)).toEqual(false);
     });

  it('should close dialog after saved', () => {
    const result = true;  // On notes editor save success will get 'true';
    notesDialog.closeAfterSave = true;
    notesDialog.saved(result);
    expect(dialogRefSpy.close).toHaveBeenCalledWith(result);
  });

  it('should show note list', () => {
    notesDialog.openList();
    expect(notesDialog.showList).toEqual(true);
  });

  it('should show notes editor', () => {
    notesDialog.openEditor({
      dialogState: NoteDialogState.EDITOR,
      noteType: NoteType.DEVICE,
      ids: [serial1],
      noteId,
      labName,
    });
    expect(notesDialog.showList).toEqual(false);
  });

  it('should show list when openEditor with incorrect params', () => {
    notesDialog.openEditor({
      dialogState: NoteDialogState.EDITOR,
      noteType: NoteType.DEVICE,
      ids: [serial1, serial2],
      noteId,
      labName,
    });
    expect(notesDialog.showList).toEqual(true);
  });
});
