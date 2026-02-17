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
import {SelectionModel} from '@angular/cdk/collections';
import {Location} from '@angular/common';
import {Component, Input, OnInit, ChangeDetectionStrategy} from '@angular/core';
import {forkJoin} from 'rxjs';
import {delay, finalize, first, mergeMap} from 'rxjs/operators';

import {MttClient} from '../services/mtt_client';
import * as mttModels from '../services/mtt_models';
import {Notifier} from '../services/notifier';
import {buildApiErrorMessage} from '../shared/util';

/** A component for selecting remote config sets to import. */
@Component({
  changeDetection: ChangeDetectionStrategy.Eager,standalone: false,
  selector: 'config-set-picker',
  styleUrls: ['config_set_picker.css'],
  templateUrl: './config_set_picker.ng.html',
})
export class ConfigSetPicker implements OnInit {
  configSetStatus = mttModels.ConfigSetStatus;
  isBuildChannelAvailable = mttModels.isBuildChannelAvailable;
  isLoading = false;
  configs: mttModels.ConfigSetInfo[] = [];
  buildChannels: mttModels.BuildChannel[] = [];

  @Input() isDialog = false;

  @Input() selectedRows = [];
  selection = new SelectionModel<mttModels.ConfigSetInfo>(
      /*allow multi select*/ true, this.configs);

  @Input()
  displayedColumns: string[] = [
    'select',
    'name',
    'description',
    'status',
  ];

  constructor(
      private readonly mttClient: MttClient,
      private readonly notifier: Notifier,
      private readonly liveAnnouncer: LiveAnnouncer,
      private readonly location: Location,
  ) {}

  ngOnInit() {
    this.load();
  }

  load() {
    this.isLoading = true;
    this.liveAnnouncer.announce('Loading config sets', 'polite');

    // Get the build channels to check for authentication
    this.mttClient.getConfigSetBuildChannels()
        .pipe(
            first(),
            mergeMap(res => {
              this.buildChannels = res.build_channels || [];
              return this.mttClient.getConfigSetInfos(
                  /*include_remote*/ true,
                  this.isDialog ? [] :
                                  [mttModels.ConfigSetStatus.NOT_IMPORTED]);
            }),
            finalize(() => {
              this.isLoading = false;
            }),
        )
        .subscribe(
            res => {
              this.liveAnnouncer.announce('Loading complete', 'assertive');
              this.configs = res.config_set_infos;
            },
            error => {
              this.notifier.showError(
                  'Failed to load config set infos.',
                  buildApiErrorMessage(error));
            },
        );
  }

  addSelectedConfigSets() {
    this.isLoading = true;
    this.liveAnnouncer.announce('Importing config sets', 'assertive');

    const configObs = [];
    for (const info of this.selection.selected) {
      configObs.push(this.mttClient.importConfigSet(info.url));
    }
    forkJoin(configObs)
        .pipe(first())
        .pipe(delay(100))  // Wait for updates before redirecting
        .pipe(finalize(() => {
          this.isLoading = false;
          this.liveAnnouncer.announce('Loading complete', 'assertive');
        }))
        .subscribe(res => {
          this.notifier.showMessage(`Configuration(s) imported`);
          if (this.isDialog) {
            // Stay in Setup Wizard stepper
            this.load();
          } else {
            // When used in Settings page, go back to list page after submitting
            this.back();
          }
        });
  }

  /**
   * On selection change, toggle the corresponding row and emit the selected
   * rows
   */
  onSelectionChange(row: mttModels.ConfigSetInfo) {
    this.selection.toggle(row);
  }

  back() {
    this.location.back();
  }
}
