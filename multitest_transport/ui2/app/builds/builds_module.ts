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

/**
 * A module for all build components and pages.
 */
import {NgModule} from '@angular/core';
import {Title} from '@angular/platform-browser';
import {RouterModule} from '@angular/router';

import {BuildChannelsModule} from '../build_channels/build_channels_module';
import {ServicesModule} from '../services/services_module';
import {SharedModule} from '../shared/shared_module';
import {TestRunsModule} from '../test_runs/test_runs_module';

import {BuildCreatePage} from './build_create_page';
import {BuildDetail} from './build_detail';
import {BuildDetailPage} from './build_detail_page';
import {BuildEditor} from './build_editor';
import {BuildFileSelector} from './build_file_selector';
import {BuildList} from './build_list';
import {BuildListPage} from './build_list_page';
import {TestRequirements} from './test_requirements';
import {XtsRequirementDetect} from './xts_requirement_detect';

const COMPONENTS = [
  BuildCreatePage,
  BuildDetail,
  BuildDetailPage,
  BuildEditor,
  BuildFileSelector,
  BuildList,
  BuildListPage,
  TestRequirements,
  XtsRequirementDetect,
];

@NgModule({
  declarations: COMPONENTS,
  providers: [Title],
  imports: [
    BuildChannelsModule,
    RouterModule,
    ServicesModule,
    SharedModule,
    TestRunsModule,
  ],
  exports: COMPONENTS,
})
export class BuildsModule {
}
