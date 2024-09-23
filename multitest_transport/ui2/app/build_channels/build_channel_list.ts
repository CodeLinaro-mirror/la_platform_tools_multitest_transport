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

import {LiveAnnouncer} from '@angular/cdk/a11y';
import {Component, OnDestroy, OnInit} from '@angular/core';
import {ReplaySubject} from 'rxjs';
import {finalize, first, takeUntil} from 'rxjs/operators';

import {MttClient} from '../services/mtt_client';
import {BuildChannel, isDefaultBuildChannel} from '../services/mtt_models';
import {Notifier} from '../services/notifier';
import {buildApiErrorMessage} from '../shared/util';

/** A component for displaying a list of build channels. */
@Component({
  standalone: false,
  selector: 'build-channel-list',
  styleUrls: ['build_channel_list.css'],
  templateUrl: './build_channel_list.ng.html',
})
export class BuildChannelList implements OnInit, OnDestroy {
  isLoading = false;
  isDefaultBuildChannel = isDefaultBuildChannel;
  buildChannels: BuildChannel[] = [];

  private readonly destroy = new ReplaySubject<void>();

  constructor(
      private readonly mtt: MttClient,
      private readonly notifier: Notifier,
      private readonly liveAnnouncer: LiveAnnouncer,
  ) {}

  ngOnInit() {
    this.load();
  }

  ngOnDestroy() {
    this.destroy.next();
    this.liveAnnouncer.clear();
  }

  load() {
    this.isLoading = true;
    this.liveAnnouncer.announce('Loading', 'polite');

    this.mtt.getBuildChannels()
        .pipe(
            takeUntil(this.destroy),
            finalize(() => {
              this.isLoading = false;
            }),
            )
        .subscribe(
            result => {
              this.buildChannels = result.build_channels || [];
              this.liveAnnouncer.announce('Build channels loaded', 'assertive');
            },
            error => {
              this.notifier.showError(
                  'Failed to load build channels.',
                  buildApiErrorMessage(error));
            },
        );
  }

  delete(buildChannel: BuildChannel) {
    this.notifier
        .confirm(
            `Do you really want to delete build channel '${
                buildChannel.name}'?`,
            'Delete build channel')
        .subscribe(result => {
          if (!result) {
            return;
          }
          this.mtt.deleteBuildChannel(buildChannel.id)
              .pipe(first())
              .subscribe(
                  result => {
                    const index = this.buildChannels.findIndex(
                        bc => bc.id === buildChannel.id);
                    this.buildChannels.splice(index, 1);
                    this.notifier.showMessage(
                        `Build channel '${buildChannel.name}' deleted`);
                  },
                  error => {
                    this.notifier.showError(
                        `Failed to delete build channel '${
                            buildChannel.name}'.`,
                        buildApiErrorMessage(error));
                  });
        });
  }
}
