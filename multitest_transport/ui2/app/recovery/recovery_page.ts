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

import {Component, OnDestroy, OnInit} from '@angular/core';
import {ActivatedRoute, ParamMap, Router} from '@angular/router';
import {ReplaySubject} from 'rxjs';
import {take, takeUntil} from 'rxjs/operators';

import {OfflineHostFilterParams} from '../services/mtt_lab_models';

/** Page for recovery bad host and bad device. */
@Component({
  standalone: false,
  selector: 'recovery-page',
  styleUrls: ['recovery_page.css'],
  templateUrl: './recovery_page.ng.html',
})
export class RecoveryPage implements OnInit, OnDestroy {
  focusedHostName = '';

  private readonly defaultFilterParams = {
    lab: '',
    hostGroups: [],
    runTargets: [],
    testHarness: '',
  };

  private readonly destroy = new ReplaySubject<void>();

  /** An object to store the parameters parsed from URL. */
  urlParams: OfflineHostFilterParams = this.defaultFilterParams;

  readonly LAB_FIELD = 'lab';
  readonly RUN_TARGETS_FIELD = 'runTargets';
  readonly HOST_GROUPS_FIELD = 'hostGroups';
  readonly TEST_HARNESS_FIELD = 'testHarness';

  constructor(
      private readonly router: Router,
      private readonly route: ActivatedRoute,
  ) {}

  ngOnInit() {
    this.route.queryParamMap
        .pipe(
            take(1),
            takeUntil(this.destroy),
            )
        .subscribe((params: ParamMap) => {
          this.urlParams = {
            lab: params.get(this.LAB_FIELD) || this.defaultFilterParams.lab,
            hostGroups: params.getAll(this.HOST_GROUPS_FIELD) ||
                this.defaultFilterParams.hostGroups,
            runTargets: params.getAll(this.RUN_TARGETS_FIELD) ||
                this.defaultFilterParams.runTargets,
            testHarness: params.get(this.TEST_HARNESS_FIELD) ||
                this.defaultFilterParams.testHarness,
          };
        });
  }

  ngOnDestroy() {
    this.destroy.next();
  }

  back() {
    this.router.navigateByUrl('/offline_hosts');
  }

  unfocusHost() {
    this.focusedHostName = '';
  }
}
