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
import {ActivatedRoute} from '@angular/router';

import {LAB_APPLICATION_NAME} from '../shared/shared_module';

/** A component for displaying the details of a host. */
@Component({
  changeDetection: ChangeDetectionStrategy.Eager,standalone: false,
  selector: 'host-details-page',
  templateUrl: './host_details_page.ng.html',
})
export class HostDetailsPage implements OnInit {
  id = '';

  constructor(
      private readonly route: ActivatedRoute, private readonly title: Title) {}

  ngOnInit() {
    this.title.setTitle(`${LAB_APPLICATION_NAME} - Host Details`);
    this.route.params.subscribe(params => {
      this.id = params['id'] || '';
    });
  }
}
