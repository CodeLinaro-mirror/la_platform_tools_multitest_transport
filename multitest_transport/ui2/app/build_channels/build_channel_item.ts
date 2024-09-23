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

import {Component, EventEmitter, Input, OnInit, Output} from '@angular/core';

import {MttClient} from '../services/mtt_client';
import {AuthorizationMethod, AuthorizationState, BuildChannel, isDefaultBuildChannel} from '../services/mtt_models';
import {Notifier} from '../services/notifier';
import {assertRequiredInput, buildApiErrorMessage, delay} from '../shared/util';

/** A component for displaying a list of build channels. */
@Component({
  standalone: false,
  selector: 'build-channel-item',
  styleUrls: ['build_channel_item.css'],
  templateUrl: './build_channel_item.ng.html',
})
export class BuildChannelItem implements OnInit {
  readonly AuthorizationMethod = AuthorizationMethod;
  readonly AuthorizationState = AuthorizationState;

  isDefault = true;

  @Input() buildChannel!: BuildChannel;
  @Input() edit = true;

  @Output() readonly authChange = new EventEmitter<BuildChannel>();
  @Output() readonly deleteItem = new EventEmitter<BuildChannel>();

  constructor(
      private readonly mtt: MttClient, private readonly notifier: Notifier) {}

  ngOnInit() {
    assertRequiredInput(
        this.buildChannel, 'buildChannel', 'build_channel_item');
    this.isDefault = isDefaultBuildChannel(this.buildChannel);
  }

  canAuthWith(method: AuthorizationMethod): boolean {
    return !!this.buildChannel.auth_methods &&
        this.buildChannel.auth_methods.includes(method);
  }

  /** Authorize a build channel with a service account JSON key. */
  uploadKeyfile(keyFile?: File) {
    if (!keyFile) {
      return;
    }
    this.mtt
        .authorizeBuildChannelWithServiceAccount(this.buildChannel.id, keyFile)
        .pipe(delay(500))  // Delay for data to be persisted
        .subscribe(
            () => {
              this.authChange.emit(this.buildChannel);
            },
            error => {
              this.notifier.showError(
                  `Failed to authorize build channel '${
                      this.buildChannel.name}'.`,
                  buildApiErrorMessage(error));
            });
  }

  /** Revoke a build channel's authorization. */
  revokeAuthorization() {
    this.mtt.unauthorizeBuildChannel(this.buildChannel.id)
        .pipe(delay(500))  // Delay for data to be persisted
        .subscribe(
            () => {
              this.authChange.emit(this.buildChannel);
            },
            error => {
              this.notifier.showError(
                  `Failed to revoke authorization for build channel '${
                      this.buildChannel.name}'.`,
                  buildApiErrorMessage(error));
            });
  }
}
