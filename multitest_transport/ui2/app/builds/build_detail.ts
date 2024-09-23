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
import {MatDialog} from '@angular/material/dialog';
import {Router} from '@angular/router';
import {interval, ReplaySubject} from 'rxjs';
import {finalize, takeUntil} from 'rxjs/operators';

import {MttClient} from '../services/mtt_client';
import * as mttModels from '../services/mtt_models';
import {Notifier} from '../services/notifier';
import {buildApiErrorMessage} from '../shared/util';

import {BuildEditor, BuildEditorData} from './build_editor';
import {XtsRequirementDetect, XtsRequirementDetectData} from './xts_requirement_detect';

/** A component for displaying the details of a build. */
@Component({
  standalone: false,
  selector: 'build-detail',
  styleUrls: ['build_detail.css'],
  templateUrl: './build_detail.ng.html',
})
export class BuildDetail implements OnInit, AfterViewInit {
  @ViewChild('backButton', {static: false}) backButton?: MatButton;
  @Input({required: true}) buildId!: string;

  isLoading = false;

  build?: mttModels.Build;

  readonly XtsRequirementsDetectionStatus =
      mttModels.XtsRequirementsDetectionStatus;

  private readonly destroy = new ReplaySubject<void>();
  private readonly DETECTABLE_STATUSES = [
    mttModels.XtsRequirementsDetectionStatus.CANCELED,
    mttModels.XtsRequirementsDetectionStatus.ERROR,
    mttModels.XtsRequirementsDetectionStatus.NOT_STARTED,
  ];
  private readonly ANDROID_PARTNER_APPROVALS_URL_PREFIX =
      'https://partner.android.com/approvals';

  get testRequirementsAvailable(): boolean {
    return this.build?.detection_status ===
        mttModels.XtsRequirementsDetectionStatus.COMPLETED;
  }

  get showDetectButton(): boolean {
    return this.DETECTABLE_STATUSES.includes(this.build!.detection_status!);
  }

  constructor(
      private readonly liveAnnouncer: LiveAnnouncer,
      private readonly matDialog: MatDialog,
      private readonly mttClient: MttClient,
      private readonly notifier: Notifier,
      private readonly router: Router,
  ) {}

  ngOnInit() {
    this.load();
    this.autoRefreshBuild();
  }

  ngAfterViewInit() {
    this.backButton!.focus();
  }

  ngOnDestroy() {
    this.destroy.next();
    this.destroy.complete();
    this.liveAnnouncer.clear();
  }

  autoRefreshBuild() {
    // Auto-load the latest build every 60 seconds.
    interval(60_000).pipe(takeUntil(this.destroy)).subscribe(() => {
      this.load();
    });
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

  getApfeBuildUrl(apfeBuildName: string): string {
    const apfeBuildUrlName = apfeBuildName.replace(new RegExp('/', 'g'), '-');
    const url = `${this.ANDROID_PARTNER_APPROVALS_URL_PREFIX}/builds/${
        apfeBuildUrlName}/overview/build-meta?a=1`;
    return url;
  }

  update() {
    const buildEditorData: BuildEditorData = {
      build: {
        name: this.build!.name,
        fingerprint: this.build!.fingerprint,
        file_url: this.build!.file_url,
        size: this.build!.size,
        labels: this.build!.labels || [],
      }
    };

    const dialogRef = this.matDialog.open(BuildEditor, {
      width: '1000px',
      height: '460px',
      panelClass: 'build-editor',
      data: buildEditorData,
    });

    dialogRef.componentInstance.buildSubmitted
        .pipe(takeUntil(dialogRef.afterClosed()))
        .subscribe((buildToUpdate: mttModels.Build) => {
          this.mttClient.builds.update(this.buildId, buildToUpdate)
              .pipe(takeUntil(this.destroy))
              .subscribe(
                  updatedBuild => {
                    this.build = updatedBuild;
                  },
                  error => {
                    this.notifier.showError(
                        `Failed to update build '${this.buildId}'.`,
                        buildApiErrorMessage(error));
                  },
              );
        });
  }

  back() {
    this.router.navigate(['builds']);
  }

  detect() {
    const initConfig = mttModels.initXtsRequirementDetect();

    const xtsRequirementDetectData:
        XtsRequirementDetectData = {testRunConfig: initConfig};

    const dialogRef = this.matDialog.open(XtsRequirementDetect, {
      width: '80vw',
      height: '80vh',
      panelClass: 'xts-requirements-detect-dialog',
      data: xtsRequirementDetectData,
    });

    dialogRef.componentInstance.configSubmitted
        .pipe(takeUntil(dialogRef.afterClosed()))
        .subscribe((newConfig: mttModels.TestRunConfig) => {
          const request: mttModels.XtsRequirementsDetectionRequest = {
            device_spec: newConfig.device_specs![0],
            test_resource_objs: newConfig.test_resource_objs!,
          };
          this.mttClient.builds.detect(this.buildId, request)
              .pipe(takeUntil(this.destroy))
              .subscribe(
                  updatedBuild => {
                    this.build = updatedBuild;
                  },
                  error => {
                    this.notifier.showError(
                        `Failed to detect xTS requirements for build '${
                            this.buildId}'.`,
                        buildApiErrorMessage(error));
                  },
              );
        });
  }
}
