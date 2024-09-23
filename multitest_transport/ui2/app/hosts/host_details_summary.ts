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
import {Component, EventEmitter, Input, OnChanges, OnDestroy, OnInit, Output, SimpleChanges} from '@angular/core';
import {ReplaySubject} from 'rxjs';
import {finalize, takeUntil} from 'rxjs/operators';

import {LabHostInfo} from '../services/mtt_lab_models';
import {Notifier} from '../services/notifier';
import {TfcClient} from '../services/tfc_client';
import {RecoveryState} from '../services/tfc_models';
import {OverflowListType} from '../shared/overflow_list';
import {assertRequiredInput} from '../shared/util';

/** Readonly form for host details summary. */
@Component({
  standalone: false,
  selector: 'host-details-summary',
  styleUrls: ['./host_details_summary.css'],
  templateUrl: './host_details_summary.ng.html',
})
export class HostDetailsSummary implements OnChanges, OnInit, OnDestroy {
  @Output() readonly dataLoadedEvent = new EventEmitter<boolean>();
  @Input() id!: string;
  private readonly destroy = new ReplaySubject<void>();
  readonly overflowListType = OverflowListType;
  readonly recoveryState = RecoveryState;

  data?: LabHostInfo;
  isLoading = false;

  constructor(
      private readonly liveAnnouncer: LiveAnnouncer,
      private readonly notifier: Notifier,
      private readonly tfcClient: TfcClient) {}

  ngOnChanges(changes: SimpleChanges) {
    if (changes['id'] && !changes['id'].firstChange) this.loadHost(this.id);
  }

  ngOnInit() {
    assertRequiredInput(this.id, 'id', 'host-detail-summary');
    this.loadHost(this.id);
  }

  ngOnDestroy() {
    this.destroy.next();
  }

  getPools(host: LabHostInfo): string[] {
    return host.pools ? host.pools : [];
  }

  /**
   * Loads the hostInfo by id.
   * @param id Unique host name
   */
  loadHost(id: string) {
    this.isLoading = true;
    this.liveAnnouncer.announce('Loading', 'polite');
    this.tfcClient.getHostInfo(id)
        .pipe(
            takeUntil(this.destroy),
            finalize(() => {
              this.isLoading = false;
            }),
            )
        .subscribe(
            result => {
              this.data = result;
              this.liveAnnouncer.announce('Host info loaded', 'assertive');
            },
            error => {
              this.notifier.showError(`Failed to load host ${id}`);
            },
        );
  }
}
