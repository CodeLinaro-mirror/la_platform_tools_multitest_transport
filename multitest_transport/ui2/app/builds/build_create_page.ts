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

import {COMMA, ENTER} from '@angular/cdk/keycodes';
import {AfterViewInit, Component, ViewChild} from '@angular/core';
import {MatButton} from '@angular/material/button';
import {MatChipInputEvent} from '@angular/material/chips';
import {MatDialog} from '@angular/material/dialog';
import {Router} from '@angular/router';
import {ReplaySubject} from 'rxjs';
import {takeUntil} from 'rxjs/operators';

import {MttClient} from '../services/mtt_client';
import * as mttModels from '../services/mtt_models';
import {Notifier} from '../services/notifier';
import {FormChangeTracker} from '../shared/can_deactivate';
import {buildApiErrorMessage} from '../shared/util';

import {BuildFileSelector, BuildFileSelectorData} from './build_file_selector';

/**
 * Component for creating a build.
 */
@Component({
  selector: 'build-create-page',
  styleUrls: ['build_create_page.css'],
  templateUrl: './build_create_page.ng.html',
})
export class BuildCreatePage extends FormChangeTracker implements
    AfterViewInit {
  @ViewChild('backButton', {static: false}) backButton?: MatButton;

  data: Partial<mttModels.Build> = mttModels.initBuild();

  /** Keys used to separate labels */
  readonly separatorKeyCodes: number[] = [ENTER, COMMA];

  private readonly destroy = new ReplaySubject<void>();

  constructor(
      private readonly mttClient: MttClient,
      private readonly notifier: Notifier,
      private readonly router: Router,
      private readonly dialog: MatDialog,
  ) {
    super();
  }

  ngAfterViewInit() {
    this.backButton!.focus();
  }

  ngOnDestroy() {
    this.destroy.next();
    this.destroy.complete();
  }

  addLabel(event: MatChipInputEvent) {
    const input = event.chipInput.inputElement;
    const value = event.value;

    if ((value || '').trim() &&
        this.data.labels!.indexOf(value.trim()) === -1) {
      this.data.labels!.push(value.trim());
    }

    if (input) {
      input.value = '';
    }
  }

  removeLabel(label: string) {
    const index = this.data.labels!.indexOf(label);
    if (index >= 0) {
      this.data.labels!.splice(index, 1);
    }
  }

  openBuildFileSelector(build: Partial<mttModels.Build>) {
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

  back() {
    this.router.navigate(['builds']);
  }

  /**
   * Validates the form.
   * Returns true if no error, false otherwise.
   */
  validate(): boolean {
    this.invalidInputs = this.getInvalidInputs();
    for (const tracker of this.trackers) {
      this.invalidInputs.push(...tracker.getInvalidInputs());
    }
    return !this.invalidInputs.length;
  }

  // Creates a build.
  submit() {
    if (!this.validate()) {
      return;
    }

    const build: mttModels.Build = {
      name: this.data.name!.trim(),
      file_url: this.data.file_url!.trim(),
      size: this.data.size || 0,
      labels: this.data.labels!,
    };
    this.mttClient.builds.create(build)
        .pipe(takeUntil(this.destroy))
        .subscribe(
            (result) => {
              super.resetForm();
              this.router.navigate([`builds/${result.id}`]);
              this.notifier.showMessage(`Build '${result.name}' created`);
            },
            (error) => {
              this.notifier.showError(
                  'Failed to create build.', buildApiErrorMessage(error));
            });
  }
}
