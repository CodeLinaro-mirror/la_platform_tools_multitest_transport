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

import {Component, EventEmitter, Input, OnInit, Output, ViewChild, ChangeDetectionStrategy} from '@angular/core';
import {Sort} from '@angular/material/sort';

import {FeedbackService} from '../services/feedback_service';
import {HostAssignInfo, LabHostInfo, SurveyTrigger} from '../services/mtt_lab_models';
import {UserService} from '../services/user_service';
import {assertRequiredInput} from '../shared/util';

import {HostListTable} from './host_list_table';

/** Displays unassigned offline hosts or hosts with offline devices. */
@Component({
  changeDetection: ChangeDetectionStrategy.Eager,standalone: false,
  selector: 'unassigned-offline-host-list',
  styleUrls: ['unassigned_offline_host_list.css'],
  templateUrl: './unassigned_offline_host_list.ng.html',
})
export class UnassignedOfflineHostList implements OnInit {
  @ViewChild(HostListTable, {static: true}) hostListTable!: HostListTable;

  /** Unassigned hosts that is provided as the data source of host list. */
  @Input() unassignedHostListDataSource: LabHostInfo[] = [];
  @Input() isLoading = false;
  @Input() labName = '';
  @Input() listHeaderRowTop = '0';
  @Input() listRowMaxHeight = 400;
  @Input() currentLabOwners: string[] = [];

  @Output() readonly assignHostsToMe = new EventEmitter<string[]>();
  @Output() readonly assignHostsTo = new EventEmitter<HostAssignInfo>();
  @Output() readonly notesUpdated = new EventEmitter<string[]>();
  @Output() readonly changeSort = new EventEmitter<Sort>();
  @Output() readonly removeHostFromList = new EventEmitter<LabHostInfo>();

  constructor(
      private readonly feedbackService: FeedbackService,
      readonly userService: UserService,
  ) {}

  ngOnInit() {
    assertRequiredInput(
        this.hostListTable, 'hostListTable', 'UnassignedOfflineHostList');
  }

  startBatchAddHostsNotesHats() {
    this.feedbackService.startSurvey(SurveyTrigger.BATCH_ADD_HOSTS_NOTES);
  }
}
