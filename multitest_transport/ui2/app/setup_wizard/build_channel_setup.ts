/**
 * Copyright 2019 Google LLC
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
import {first} from 'rxjs/operators';

import {MttClient} from '../services/mtt_client';
import {BuildChannel} from '../services/mtt_models';

/** Default Google Drive build channel ID. */
const GOOGLE_DRIVE_ID = 'google_drive';

/** Allows users to authenticate their Google Drive build channel. */
@Component({
  standalone: false,
  selector: 'build-channel-setup',
  styleUrls: ['build_channel_setup.css'],
  templateUrl: './build_channel_setup.ng.html',
})
export class BuildChannelSetup implements OnInit {
  driveBuildChannel?: BuildChannel;

  constructor(private readonly mtt: MttClient) {}

  ngOnInit() {
    this.load();
  }

  load() {
    this.mtt.getBuildChannels().pipe(first()).subscribe(result => {
      this.driveBuildChannel = (result.build_channels || [])
          .find(bc => bc.id === GOOGLE_DRIVE_ID);
    });
  }
}
