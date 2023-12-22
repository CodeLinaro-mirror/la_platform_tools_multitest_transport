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

import {LiveAnnouncer} from '@angular/cdk/a11y';
import {AfterViewInit, Component, Input, OnInit, ViewChild} from '@angular/core';
import {MatButton} from '@angular/material/button';
import {Router} from '@angular/router';
import {ReplaySubject} from 'rxjs';
import {finalize, takeUntil} from 'rxjs/operators';

import {MttClient} from '../services/mtt_client';
import * as mttModels from '../services/mtt_models';
import {Notifier} from '../services/notifier';
import {buildApiErrorMessage} from '../shared/util';

/** A component for displaying the details of a build. */
@Component({
  selector: 'build-detail',
  styleUrls: ['build_detail.css'],
  templateUrl: './build_detail.ng.html',
})
export class BuildDetail implements OnInit, AfterViewInit {
  @ViewChild('backButton', {static: false}) backButton?: MatButton;
  @Input({required: true}) buildId!: string;

  isLoading = false;

  build?: mttModels.Build;

  private readonly destroy = new ReplaySubject<void>();

  constructor(
      private readonly liveAnnouncer: LiveAnnouncer,
      private readonly mttClient: MttClient,
      private readonly notifier: Notifier,
      private readonly router: Router,
  ) {}

  ngOnInit() {
    this.load();
  }

  ngAfterViewInit() {
    this.backButton!.focus();
  }

  ngOnDestroy() {
    this.destroy.next();
    this.destroy.complete();
    this.liveAnnouncer.clear();
  }

  load() {
    this.isLoading = true;
    this.liveAnnouncer.announce('Loading', 'polite');

    this.mttClient.builds.get(this.buildId)
        .pipe(
            takeUntil(this.destroy),
            finalize(() => {
              this.isLoading = false;
            }),
            )
        .subscribe(
            result => {
              this.build = result;
              this.liveAnnouncer.announce('Build loaded', 'assertive');
            },
            error => {
              this.notifier.showError(
                  `Failed to load build '${this.buildId}'.`,
                  buildApiErrorMessage(error));
            },
        );
  }

  back() {
    this.router.navigate(['builds']);
  }
}
