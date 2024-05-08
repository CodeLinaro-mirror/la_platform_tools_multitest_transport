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

import {COMMA, ENTER} from '@angular/cdk/keycodes';
import {Component, EventEmitter, Inject, Output} from '@angular/core';
import {MatChipInputEvent} from '@angular/material/chips';
import {MAT_DIALOG_DATA, MatDialog, MatDialogRef} from '@angular/material/dialog';
import {ReplaySubject} from 'rxjs';
import {takeUntil} from 'rxjs/operators';

import {MttClient} from '../services/mtt_client';
import * as mttModels from '../services/mtt_models';
import {Notifier} from '../services/notifier';
import {FormChangeTracker} from '../shared/can_deactivate';
import {buildApiErrorMessage} from '../shared/util';

import {BuildFileSelector, BuildFileSelectorData} from './build_file_selector';

/**
 * Data passed when opening the dialog to update a build.
 * @param build: the build to update.
 */
export interface BuildEditorData {
  build: mttModels.Build;
}

/**
 * Component for updating a build.
 */
@Component({
  selector: 'build-editor',
  styleUrls: ['build_editor.css'],
  templateUrl: './build_editor.ng.html',
  providers: [{provide: FormChangeTracker, useExisting: BuildEditor}]
})
export class BuildEditor extends FormChangeTracker {
  @Output() readonly buildSubmitted = new EventEmitter<mttModels.Build>();

  readonly separatorKeyCodes: number[] = [ENTER, COMMA];

  private readonly destroy = new ReplaySubject<void>();

  constructor(
      @Inject(MAT_DIALOG_DATA) public data: BuildEditorData,
      private readonly mttClient: MttClient,
      private readonly notifier: Notifier, private readonly dialog: MatDialog,
      private readonly dialogRef: MatDialogRef<BuildEditor>) {
    super();
  }

  addLabel(event: MatChipInputEvent) {
    const input = event.chipInput.inputElement;
    const value = event.value;

    if ((value || '').trim() &&
        this.data.build.labels.indexOf(value.trim()) === -1) {
      this.data.build.labels.push(value.trim());
    }

    if (input) {
      input.value = '';
    }
  }

  removeLabel(label: string) {
    const index = this.data.build.labels.indexOf(label);
    if (index >= 0) {
      this.data.build.labels.splice(index, 1);
    }
  }

  openBuildFileSelector(build: mttModels.Build) {
    const data: BuildFileSelectorData = {fileUrl: build.file_url!};
    const dialogRef = this.dialog.open(BuildFileSelector, {
      width: '800px',
      height: '600px',
      panelClass: 'build-selector-container',
      data
    });

    dialogRef.afterClosed().subscribe(fileUrl => {
      if (fileUrl) {
        build.file_url = fileUrl;
        this.mttClient.lookupBuildItem(fileUrl)
            .pipe(takeUntil(this.destroy))
            .subscribe(
                (res) => {
                  build.size = res.size;
                },
                (error) => {
                  this.notifier.showError(
                      'Failed to lookup build item.',
                      buildApiErrorMessage(error));
                },
            );
      }
    });
  }

  validate(): boolean {
    this.invalidInputs = this.getInvalidInputs();
    for (const tracker of this.trackers) {
      this.invalidInputs.push(...tracker.getInvalidInputs());
    }
    return !this.invalidInputs.length;
  }

  updateAndClose() {
    if (!this.validate()) {
      return;
    }

    this.buildSubmitted.emit(this.data.build);
    this.dialogRef.close();
  }
}
