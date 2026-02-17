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

import {LiveAnnouncer} from '@angular/cdk/a11y';
import {Component, Input, OnChanges, OnDestroy, OnInit, SimpleChanges, ChangeDetectionStrategy} from '@angular/core';
import {ReplaySubject} from 'rxjs';
import {takeUntil} from 'rxjs/operators';

import {Notifier} from '../services/notifier';
import {TfcClient} from '../services/tfc_client';
import {DeviceCountSummary} from '../services/tfc_models';
import {assertRequiredInput} from '../shared/util';

/** Display a list of devices count summaries from a host. */
@Component({
  changeDetection: ChangeDetectionStrategy.Eager,standalone: false,
  selector: 'host-details-device-count-summaries',
  styleUrls: ['host_details_device_count_summaries.css'],
  templateUrl: './host_details_device_count_summaries.ng.html',
})
export class HostDetailsDeviceCountSummaries implements OnChanges, OnDestroy,
                                                        OnInit {
  private readonly destroy = new ReplaySubject<void>();
  @Input() id!: string;
  data: DeviceCountSummary[] = [];
  displayedColumns: string[] = [
    'run_target',
    'total',
    'offline',
    'available',
    'allocated',
  ];

  constructor(
      private readonly liveAnnouncer: LiveAnnouncer,
      private readonly notifier: Notifier,
      private readonly tfcClient: TfcClient,

  ) {}

  ngOnChanges(changes: SimpleChanges) {
    if (changes['id'] && !changes['id'].firstChange) this.load(this.id);
  }

  ngOnInit() {
    assertRequiredInput(this.id, 'id', 'HostDetailsDeviceCountSummaries');
    this.load(this.id);
  }

  ngOnDestroy() {
    this.destroy.next();
  }

  load(hostname: string) {
    this.liveAnnouncer.announce('Loading', 'polite');
    this.tfcClient.getHostInfo(hostname)
        .pipe(takeUntil(this.destroy))
        .subscribe(
            result => {
              this.data = result ? result.device_count_summaries || [] : [];
              this.liveAnnouncer.announce(
                  'Device count summaries loaded', 'assertive');
            },
            error => {
              this.notifier.showError(
                  `Failed to load device count summaries for host ${hostname}`);
            },
        );
  }
}
