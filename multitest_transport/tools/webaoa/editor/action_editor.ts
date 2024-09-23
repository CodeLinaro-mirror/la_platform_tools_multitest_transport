/**
 * @license
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

import {AoaAction, AoaActionCommand, COMMANDS} from './action';

/** Editor result containing the updated action and the execution flag. */
export interface AoaActionEditorResult {
  action: AoaAction;
  execute: boolean;
}

/** Dialog used to edit AOA actions. */
@Component({
  standalone: false,
  selector: 'action-editor',
  templateUrl: './action_editor.ng.html',
  styleUrls: ['./action_editor.css'],
})
export class AoaActionEditor {
  COMMANDS: readonly AoaActionCommand[] = COMMANDS;
  /** Selected command and its arguments. */
  command: AoaActionCommand;
  arguments: string;

  constructor(
      private readonly dialogRef: MatDialogRef<AoaActionEditor>,
      @Inject(MAT_DIALOG_DATA) readonly data: string) {
    const command = data.split(' ', 1)[0].toLowerCase() as AoaActionCommand;
    this.command = COMMANDS.includes(command) ? command : 'click';
    this.arguments = data.substring(command.length + 1);
  }

  /** @returns the current expression which may be invalid. */
  get expression(): string {
    return [this.command, this.arguments].filter(Boolean).join(' ');
  }

  /** @returns true if the current expression is valid. */
  get valid(): boolean {
    try {
      AoaAction.parse(this.expression);
      return true;
    } catch {
      return false;
    }
  }

  /**
   * Closes the editor and returns the updated action.
   * @param execute true to execute the action after updating
   */
  saveAndClose(execute: boolean) {
    this.dialogRef.close({action: AoaAction.parse(this.expression), execute});
  }
}
