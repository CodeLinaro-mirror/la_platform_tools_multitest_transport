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

import {Component, EventEmitter, Input, OnDestroy, Output} from '@angular/core';
import {MatDialog, MatDialogRef} from '@angular/material/dialog';
import {ReplaySubject} from 'rxjs';
import {takeUntil} from 'rxjs/operators';

import {NoteDialogParams, NoteDialogState, NotesDialog} from '../notes/notes_dialog';
import {NoteType} from '../services/mtt_lab_models';

/** Opens a notes dialog for hosts or devices. */
@Component({
  selector: 'add-notes-button',
  templateUrl: './add_notes_button.ng.html',
})
export class AddNotesButton implements OnDestroy {
  @Input() buttonStyle = 'Default';
  @Input() ids: string[] = [];
  @Input() noteType: NoteType = NoteType.DEVICE;
  @Input() labName = '';
  @Input() disabled = false;
  @Input() deviceHostMap: Array<[string, string]> = [];
  @Output() readonly notesUpdated = new EventEmitter<string[]>();
  @Output() readonly click = new EventEmitter<MouseEvent>();

  protected readonly destroy = new ReplaySubject<void>();

  constructor(readonly matDialog: MatDialog) {}

  ngOnDestroy() {
    this.destroy.next();
  }

  openNoteCreateEditor(event: MouseEvent) {
    event.stopPropagation();

    const params: NoteDialogParams = {
      dialogState: NoteDialogState.EDITOR,
      noteType: this.noteType,
      ids: this.ids,
      deviceHostMap: this.deviceHostMap,
      labName: this.labName,
    };
    this.openNotesDialog(params)
        .afterClosed()
        .pipe(takeUntil(this.destroy))
        .subscribe(result => {
          if (result) {
            this.notesUpdated.emit(this.ids);
          }
        });
  }

  openNotesDialog(params: NoteDialogParams): MatDialogRef<NotesDialog> {
    return this.matDialog.open(NotesDialog, {
      height: '600px',
      width: '1200px',
      data: params,
      autoFocus: false,
    });
  }
}
