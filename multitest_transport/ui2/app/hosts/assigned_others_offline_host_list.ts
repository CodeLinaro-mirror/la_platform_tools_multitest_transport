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

import {Component, EventEmitter, Input, OnInit, Output, ViewChild} from '@angular/core';
import {Sort} from '@angular/material/sort';

import {HostAssignInfo, LabHostInfo} from '../services/mtt_lab_models';
import {UserService} from '../services/user_service';
import {assertRequiredInput} from '../shared/util';

import {HostListTable} from './host_list_table';

/** Displays assigned to others offline hosts or hosts with offline devices. */
@Component({
  standalone: false,
  selector: 'assigned-others-offline-host-list',
  styleUrls: ['assigned_others_offline_host_list.css'],
  templateUrl: './assigned_others_offline_host_list.ng.html',
})
export class AssignedOthersOfflineHostList implements OnInit {
  @ViewChild(HostListTable, {static: true}) hostListTable!: HostListTable;

  @Input() assignedOthersHostListDataSource: LabHostInfo[] = [];
  @Input() currentLabOwners: string[] = [];
  @Input() isLoading = false;
  @Input() labName = '';
  @Input() listHeaderRowTop = '0';
  @Input() listRowMaxHeight = 400;
  @Output() readonly assignHostsTo = new EventEmitter<HostAssignInfo>();
  @Output() readonly changeSort = new EventEmitter<Sort>();

  constructor(
      readonly userService: UserService,
  ) {}

  ngOnInit() {
    assertRequiredInput(
        this.hostListTable, 'hostListTable', 'AssignedOthersOfflineHostList');
  }
}
