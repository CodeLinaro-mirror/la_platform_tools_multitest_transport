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

import {Component, OnInit} from '@angular/core';
import {Title} from '@angular/platform-browser';
import {ActivatedRoute} from '@angular/router';

import {APPLICATION_NAME} from '../shared/shared_module';

/** A component for a build detail page. */
@Component({
  selector: 'build-detail-page',
  templateUrl: './build_detail_page.ng.html',
})
export class BuildDetailPage implements OnInit {
  buildId = '';

  constructor(
      private readonly route: ActivatedRoute, private readonly title: Title) {}

  ngOnInit() {
    this.route.params.subscribe(params => {
      this.buildId = params['id'] || '';
    });
    this.title.setTitle(`${APPLICATION_NAME} - Build ${this.buildId}`);
  }
}
