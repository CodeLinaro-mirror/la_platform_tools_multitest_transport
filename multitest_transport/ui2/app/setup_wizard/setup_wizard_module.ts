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

/**
 * A module for the setup wizard flow
 */
import {NgModule} from '@angular/core';
import {MatDialogModule} from '@angular/material/dialog';
import {Title} from '@angular/platform-browser';

import {BuildChannelsModule} from '../build_channels/build_channels_module';
import {ConfigSetsModule} from '../config_sets/config_sets_module';
import {SettingsModule} from '../settings/settings_module';
import {SharedModule} from '../shared/shared_module';

import {BuildChannelSetup} from './build_channel_setup';
import {ConfigRestoreStep} from './config_restore_step';
import {DefaultAuthStep} from './default_auth_step';
import {SetupWizardDialog} from './setup_wizard_dialog';
import {SetupWizardStepper} from './setup_wizard_stepper';
import {WifiSetup} from './wifi_setup';

const COMPONENTS = [
  BuildChannelSetup, ConfigRestoreStep, DefaultAuthStep, SetupWizardDialog,
  SetupWizardStepper, WifiSetup
];

@NgModule({
  declarations: COMPONENTS,
  providers: [Title],
  imports: [
    BuildChannelsModule,
    ConfigSetsModule,
    MatDialogModule,
    SettingsModule,
    SharedModule,
  ],
  exports: COMPONENTS,
  })
export class SetupWizardModule {
}
