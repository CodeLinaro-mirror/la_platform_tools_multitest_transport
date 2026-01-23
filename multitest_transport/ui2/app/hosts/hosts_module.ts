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

import {NgModule} from '@angular/core';
import {ReactiveFormsModule} from '@angular/forms';
import {MatSlideToggleModule} from '@angular/material/slide-toggle';
import {RouterModule} from '@angular/router';
import {ServicesModule} from 'google3/third_party/py/multitest_transport/ui2/app/services';
import {SharedModule as MttSharedModule} from 'google3/third_party/py/multitest_transport/ui2/app/shared';

import {DevicesModule} from '../devices/devices_module';
import {NotesModule} from '../notes/notes_module';
import {SharedModule} from '../shared/shared_module';

import {AssignToFilter} from './assign_to_filter';
import {AssignedMeOfflineHostList} from './assigned_me_offline_host_list';
import {AssignedOthersOfflineHostList} from './assigned_others_offline_host_list';
import {DeviceCountInfoPipe} from './device_count_info_pipe';
import {HostDetails} from './host_details';
import {HostDetailsDeviceCountSummaries} from './host_details_device_count_summaries';
import {HostDetailsDeviceList} from './host_details_device_list';
import {HostDetailsExtraInfos} from './host_details_extra_infos';
import {HostDetailsHistory} from './host_details_history';
import {HostDetailsHostResource} from './host_details_host_resource';
import {HostDetailsPage} from './host_details_page';
import {HostDetailsSummary} from './host_details_summary';
import {HostList} from './host_list';
import {HostListPage} from './host_list_page';
import {HostListTable} from './host_list_table';
import {HostUpdateDialog} from './host_update_dialog';
import {HostsMarkAsVerifiedButton} from './hosts_mark_as_verified_button';
import {MarkHostAsFixedButton} from './mark_host_as_fixed_button';
import {OfflineHostAssignmentsPage} from './offline_host_assignments_page';
import {OfflineHostList} from './offline_host_list';
import {OfflineHostListPage} from './offline_host_list_page';
import {TotalOfflineDevicesAlertIconPipe} from './total_offline_devices_alert_icon_pipe';
import {UnassignedOfflineHostList} from './unassigned_offline_host_list';

const COMPONENTS = [
  AssignedMeOfflineHostList,
  AssignedOthersOfflineHostList,
  AssignToFilter,
  DeviceCountInfoPipe,
  HostDetails,
  HostDetailsDeviceCountSummaries,
  HostDetailsDeviceList,
  HostDetailsExtraInfos,
  HostDetailsHistory,
  HostDetailsHostResource,
  HostDetailsPage,
  HostDetailsSummary,
  HostList,
  HostListPage,
  HostListTable,
  HostsMarkAsVerifiedButton,
  HostUpdateDialog,
  MarkHostAsFixedButton,
  OfflineHostAssignmentsPage,
  OfflineHostList,
  OfflineHostListPage,
  TotalOfflineDevicesAlertIconPipe,
  UnassignedOfflineHostList,
];

@NgModule({
  declarations: COMPONENTS,
  imports: [
    DevicesModule,
    MatSlideToggleModule,
    MttSharedModule,
    NotesModule,
    RouterModule,
    ReactiveFormsModule,
    SharedModule,
    ServicesModule,
  ],
  exports: COMPONENTS,
})
export class HostsModule {
}
