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

import {Component, Inject, OnInit, ChangeDetectionStrategy} from '@angular/core';
import {Title} from '@angular/platform-browser';

import {APP_DATA, AppData} from '../services';
import {APPLICATION_NAME, LAB_APPLICATION_NAME} from '../shared/shared_module';

/** Displaying a list of hosts. */
@Component({
  changeDetection: ChangeDetectionStrategy.Eager,standalone: false,
  selector: 'host-list-page',
  templateUrl: './host_list_page.ng.html',
})
export class HostListPage implements OnInit {
  constructor(
      private readonly title: Title,
      @Inject(APP_DATA) private readonly appData: AppData,
  ) {}
  headerTitle = 'Hosts';
  ngOnInit() {
    this.title.setTitle(`${
        this.appData.isAtsLabInstance ?
            LAB_APPLICATION_NAME :
            APPLICATION_NAME} - ${this.headerTitle}`);
  }
}
