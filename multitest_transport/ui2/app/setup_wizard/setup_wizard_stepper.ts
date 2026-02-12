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

import {Component, ViewChild, ChangeDetectionStrategy} from '@angular/core';
import {MatStepper} from '@angular/material/stepper';
import {forkJoin, Observable} from 'rxjs';
import {first} from 'rxjs/operators';

import {MttClient} from '../services/mtt_client';
import {PrivateNodeConfig} from '../services/mtt_models';
import {Notifier} from '../services/notifier';
import * as util from '../shared/util';

import {WifiSetup} from './wifi_setup';

/**
 * A component for the stepper section of the setup wizard
 */
@Component({
  changeDetection: ChangeDetectionStrategy.Eager,standalone: false,
  selector: 'setup-wizard-stepper',
  styleUrls: ['setup_wizard_stepper.css'],
  templateUrl: './setup_wizard_stepper.ng.html',
})
export class SetupWizardStepper {
  @ViewChild('stepper', {static: false}) stepper!: MatStepper;
  @ViewChild(WifiSetup, {static: false}) wifiSetup!: WifiSetup;

  constructor(
      private readonly mtt: MttClient, private readonly notifier: Notifier) {}

  submit() {
    // Get current node config
    this.mtt.getPrivateNodeConfig().pipe(first()).subscribe(
        result => {
          const privateNodeConfig: PrivateNodeConfig = result;

          // Mark setup wizard as completed
          privateNodeConfig.setup_wizard_completed = true;

          // Submit data
          const observables: Array<Observable<unknown>> = [];
          observables.push(this.mtt.updatePrivateNodeConfig(privateNodeConfig));
          if (this.wifiSetup) {
            observables.push(this.wifiSetup.submit());
          }

          // Wait for response
          forkJoin(observables)
              .pipe(first())
              .subscribe(
                  result => {
                    // TODO: Enable metrics without reloading
                    util.reloadPage(100);
                  },
                  error => {
                    this.notifier.showError(
                        'Failed to mark setup wizard as completed.',
                        util.buildApiErrorMessage(error));
                  });
        },
        error => {
          this.notifier.showError(
              'Failed to load current settings.',
              util.buildApiErrorMessage(error));
        });
  }
}
