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

import {Component, OnInit, ChangeDetectionStrategy} from '@angular/core';
import {Title} from '@angular/platform-browser';

import {LAB_APPLICATION_NAME} from '../shared/shared_module';

/**
 * A component for displaying a list of offline hosts and hosts with offline
 * devices.
 */
@Component({
  changeDetection: ChangeDetectionStrategy.Eager,standalone: false,
  selector: 'offline-host-list-page',
  styleUrls: ['offline_host_list_page.css'],
  templateUrl: './offline_host_list_page.ng.html',
})
export class OfflineHostListPage implements OnInit {
  constructor(private readonly title: Title) {}

  ngOnInit() {
    this.title.setTitle(`${LAB_APPLICATION_NAME} - Offline Hosts & Devices`);
  }
}
