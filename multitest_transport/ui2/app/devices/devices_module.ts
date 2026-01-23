/**
 * Copyright 2020 Google LLC
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
 * A module for devices page
 */
import {NgModule} from '@angular/core';
import {ReactiveFormsModule} from '@angular/forms';
import {MatSlideToggleModule} from '@angular/material/slide-toggle';
import {Title} from '@angular/platform-browser';
import {RouterModule} from '@angular/router';

import {NotesModule} from '../notes/notes_module';
import {ServicesModule} from '../services';
import {SharedModule} from '../shared/shared_module';

import {DeviceDetails} from './device_details';
import {DeviceDetailsExtraInfos} from './device_details_extra_infos';
import {DeviceDetailsHistory} from './device_details_history';
import {DeviceDetailsPage} from './device_details_page';
import {DeviceDetailsSummary} from './device_details_summary';
import {DeviceList} from './device_list';
import {DeviceListPage} from './device_list_page';
import {DeviceListTable} from './device_list_table';
import {SimpleDeviceList} from './simple_device_list';

const COMPONENTS = [
  DeviceDetails,
  DeviceDetailsExtraInfos,
  DeviceDetailsHistory,
  DeviceDetailsPage,
  DeviceDetailsSummary,
  DeviceListTable,
  DeviceList,
  DeviceListPage,
  SimpleDeviceList,
];

@NgModule({
  declarations: COMPONENTS,
  providers: [Title],
  imports: [
    MatSlideToggleModule,
    NotesModule,
    ReactiveFormsModule,
    RouterModule,
    ServicesModule,
    SharedModule,
  ],
  exports: COMPONENTS,
})
export class DevicesModule {
}
