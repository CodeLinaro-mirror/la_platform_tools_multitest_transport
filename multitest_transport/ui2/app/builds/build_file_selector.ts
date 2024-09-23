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

import {Component, Inject} from '@angular/core';
import {MAT_DIALOG_DATA, MatDialogRef} from '@angular/material/dialog';

/**
 * Data passed when opening the dialog to select a file for a build.
 * @param fileUrl: the file URL of a build.
 */
export interface BuildFileSelectorData {
  fileUrl: string;
}

/**
 * Component to select a resource file for a build.
 */
@Component({
  standalone: false,
  selector: 'build-file-selector',
  styleUrls: ['build_file_selector.css'],
  templateUrl: './build_file_selector.ng.html',
})
export class BuildFileSelector {
  constructor(
      @Inject(MAT_DIALOG_DATA) public data: BuildFileSelectorData,
      private readonly dialogRef: MatDialogRef<BuildFileSelector>) {}

  /** Close the dialog and return the selected file URL. */
  selectAndClose() {
    this.dialogRef.close(this.data.fileUrl);
  }
}
