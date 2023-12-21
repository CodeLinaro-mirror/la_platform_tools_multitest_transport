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

import {ServicesModule} from '../services/services_module';
import {SharedModule} from '../shared/shared_module';

import {BuildCreatePage} from './build_create_page';
import {BuildDetail} from './build_detail';
import {BuildDetailPage} from './build_detail_page';
import {BuildFileSelector} from './build_file_selector';
import {BuildList} from './build_list';
import {BuildListPage} from './build_list_page';

const COMPONENTS = [
  BuildCreatePage,
  BuildDetail,
  BuildDetailPage,
  BuildFileSelector,
  BuildList,
  BuildListPage,
];

@NgModule({
  declarations: COMPONENTS,
  providers: [Title],
  imports: [
    RouterModule,
    ServicesModule,
    SharedModule,
  ],
  exports: COMPONENTS,
})
export class BuildsModule {
}
