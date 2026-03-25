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
 * A module for build channels page
 */
import {NgModule} from '@angular/core';
import {RouterModule} from '@angular/router';

import {BuildChannelsModule} from '../build_channels/build_channels_module';
import {ConfigSetsModule} from '../config_sets/config_sets_module';
import {DeviceActionsModule} from '../device_actions/device_actions_module';
import {SharedModule} from '../shared/shared_module';
import {TestRunActionsModule} from '../test_run_actions/test_run_actions_module';
import {FileCleanerModule} from '../file_cleaner/file_cleaner_module';

import {NotificationsForm} from './notifications_form';
import {SettingForm} from './setting_form';
import {SettingPage} from './setting_page';

const COMPONENTS = [SettingPage, SettingForm, NotificationsForm];

@NgModule({
  declarations: COMPONENTS,
  imports: [
    SharedModule,
    RouterModule,
    BuildChannelsModule,
    ConfigSetsModule,
    DeviceActionsModule,
    TestRunActionsModule,
    FileCleanerModule,
  ],
  exports: COMPONENTS,
})
export class SettingsModule {
}
