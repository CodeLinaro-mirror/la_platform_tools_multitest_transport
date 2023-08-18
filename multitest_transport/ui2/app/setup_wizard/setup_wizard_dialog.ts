/**
 * Copyright 2019 Google LLC
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

import {Component} from '@angular/core';
import {MatDialog, MatDialogRef} from '@angular/material/dialog';
import {first, mergeMap} from 'rxjs/operators';

import {MttClient} from '../services/mtt_client';
import {PrivateNodeConfig} from '../services/mtt_models';
import {Notifier} from '../services/notifier';
import * as util from '../shared/util';

import {SetupWizardStepper} from './setup_wizard_stepper';

/**
 * A component for the setup wizard overlay
 */
@Component({
  selector: 'setup-wizard-dialog',
  styleUrls: ['setup_wizard_dialog.css'],
  templateUrl: './setup_wizard_dialog.ng.html',
})
export class SetupWizardDialog {
  enableMetrics = true;
  stepperDialog!: MatDialogRef<SetupWizardStepper>;

  constructor(
      private readonly dialog: MatDialog, private readonly mtt: MttClient,
      private readonly notifier: Notifier) {}

  submitMetrics(enableMetrics: boolean) {
    // Get current node config
    this.mtt.getPrivateNodeConfig()
        .pipe(
            first(),
            mergeMap((config) => {
              config.metrics_enabled = enableMetrics;
              return this.mtt.updatePrivateNodeConfig(config);
            }),
            )
        .subscribe(
            result => {
              this.openStepper();
            },
            error => {
              this.notifier.showError(
                  'Failed to update settings.',
                  util.buildApiErrorMessage(error));
            });
  }

  openStepper() {
    this.stepperDialog = this.dialog.open(SetupWizardStepper, {
      disableClose: true,
      height: '1000px',
      width: '1000px',
    });
  }
}
