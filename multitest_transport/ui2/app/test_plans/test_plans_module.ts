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
 * A module for test plan list page
 */
import {NgModule} from '@angular/core';
import {ReactiveFormsModule} from '@angular/forms';
import {MatStepperModule} from '@angular/material/stepper';
import {Title} from '@angular/platform-browser';
import {RouterModule} from '@angular/router';

import {BuildChannelsModule} from '../build_channels/build_channels_module';
import {DeviceActionsModule} from '../device_actions/device_actions_module';
import {DevicesModule} from '../devices/devices_module';
import {SharedModule} from '../shared/shared_module';
import {TestRunsModule} from '../test_runs/test_runs_module';

import {TestPlanEditPage} from './test_plan_edit_page';
import {TestPlanList} from './test_plan_list';
import {TestPlanListPage} from './test_plan_list_page';
import {TestRunActionsModule} from '../test_run_actions/test_run_actions_module';
import {EditTestSuitesPage} from './edit_test_suites_page';

const COMPONENTS = [
  TestPlanEditPage,
  TestPlanList,
  TestPlanListPage,
  EditTestSuitesPage,
];

@NgModule({
  declarations: COMPONENTS,
  providers: [Title],
  imports: [
    BuildChannelsModule,
    DeviceActionsModule,
    DevicesModule,
    MatStepperModule,
    ReactiveFormsModule,
    RouterModule,
    SharedModule,
    TestRunActionsModule,
    TestRunsModule,
  ],
  exports: COMPONENTS,
})
export class TestPlansModule {
}
