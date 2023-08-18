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

import {Component, Inject} from '@angular/core';
import {MAT_DIALOG_DATA, MatDialogRef} from '@angular/material/dialog';
import {Notifier} from 'google3/third_party/py/multitest_transport/ui2/app/services/notifier';

import {NoteType} from '../services/mtt_lab_models';

/** Possible states for a note dialog. */
export enum NoteDialogState {
  LIST = 'LIST',
  EDITOR = 'EDITOR',
}

/**
 * Params for the notes dialog. Using noteType = DEVICE on below samples.
 * 1. Display note list of a device. { dialogState = LIST, noteType = DEVICE,
 * ids = ['id'] }
 * 2. Add note to a device. { dialogState = EDITOR, noteType = DEVICE, ids =
 * ['id']}
 * 3. Add note to multiple devices. { dialogState = EDITOR, noteType = DEVICE,
 * ids = ['id1', 'id2']}
 * 4. Edit a existing note. { dialogState = EDITOR, noteType = DEVICE, ids
 * =['id'], noteId = 324}
 */
export interface NoteDialogParams {
  /** Diaply a list or a editor. */
  dialogState: NoteDialogState;
  /**
   * A device serial list or a hostname list. Only work on
   * dialog_state='EDITOR'.
   */
  ids: string[];
  /** Query for predefined messages from a lab. */
  labName: string;
  /** Used for adding/editing a device note. */
  deviceHostMap?: Array<[string, string]>;
  /** The unique note to edit. */
  noteId?: number;
  noteType: NoteType;
}

/** Component that displays note list or note editor. */
@Component({
  selector: 'notes-dialog',
  styleUrls: ['notes_dialog.css'],
  templateUrl: './notes_dialog.ng.html',
})
export class NotesDialog {
  /** For dialogState = LIST, only can display a device's or a host's notes. */
  id?: string;
  /** To determine edit note for device or host. */
  noteType!: NoteType;
  /** According the params to display the list or the editor. */
  showList = false;
  /** When open the editor from caller, close this dialog after save. */
  closeAfterSave = false;

  constructor(
      @Inject(MAT_DIALOG_DATA) protected params: NoteDialogParams,
      private readonly dialogRef: MatDialogRef<NotesDialog>,
      private readonly notifier: Notifier,
  ) {
    if (this.validateParams(params) === false) {
      notifier.showError(`Invalid params`);
      this.dialogRef.close(false);
    }
    this.showList = params.dialogState === NoteDialogState.LIST;
    this.closeAfterSave = params.dialogState === NoteDialogState.EDITOR;
    this.noteType = params.noteType;
    if (params.ids.length === 1) this.id = params.ids[0];
  }

  /** Allow list of the params. */
  validateParams(params: NoteDialogParams): boolean {
    // Case 1: When display a list, id.length must 1.
    if (params.dialogState === NoteDialogState.LIST) {
      if (params.ids.length === 1 && !params.noteId) {
        return true;
      }
    } else {  // EDITOR
      // Case 2&3: Add note
      if (params.ids.length > 0 && !params.noteId) {
        return true;
      }
      // Case 4: Edit a existing note
      else if (params.noteId && params.ids.length === 1) {
        return true;
      }
    }
    return false;
  }

  /** Pass the results of editing. */
  saved(result: boolean) {
    if (result === true) {
      if (this.closeAfterSave) {
        this.dialogRef.close(result);
      } else {
        this.showList = true;
      }
    }
  }

  /** Click add or edit notes button on the note_list will open the editor. */
  openEditor(params: NoteDialogParams) {
    if (this.validateParams(params) === false) {
      this.showList = true;
      this.notifier.showError(`Invalid params`);
    } else {
      this.showList = false;
      this.params = params;
    }
  }

  /** Open note list. For editor back to list mode. */
  openList() {
    this.showList = true;
  }
}
