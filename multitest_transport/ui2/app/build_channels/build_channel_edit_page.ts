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
import {Location} from '@angular/common';
import {AfterViewInit, Component, OnDestroy, OnInit, ViewChild} from '@angular/core';
import {MatButton} from '@angular/material/button';
import {ActivatedRoute, Params, Router} from '@angular/router';
import {forkJoin, of as observableOf, ReplaySubject} from 'rxjs';
import {first, takeUntil} from 'rxjs/operators';

import {MttClient} from '../services/mtt_client';
import {BuildChannelConfig, BuildChannelProvider} from '../services/mtt_models';
import {Notifier} from '../services/notifier';
import {FormChangeTracker} from '../shared/can_deactivate';
import {buildApiErrorMessage} from '../shared/util';

/**
 * Build Channel Edit Page
 */
@Component({
  standalone: false,
  selector: 'build-channel-edit-page',
  styleUrls: ['build_channel_edit_page.css'],
  templateUrl: './build_channel_edit_page.ng.html',
})
export class BuildChannelEditPage extends FormChangeTracker implements
    OnInit, AfterViewInit, OnDestroy {
  @ViewChild('backButton', {static: false}) backButton?: MatButton;
  data: BuildChannelConfig = {id: '', name: '', provider_name: '', options: []};
  providers: BuildChannelProvider[] = [];
  editMode = false;
  private readonly destroy = new ReplaySubject<void>();
  isLoading = false;

  constructor(
      private readonly mttClient: MttClient,
      private readonly notifier: Notifier,
      private readonly route: ActivatedRoute,
      private readonly location: Location,
      router: Router,
      private readonly liveAnnouncer: LiveAnnouncer,
  ) {
    super();
  }

  ngOnDestroy() {
    this.destroy.next();
  }

  ngOnInit() {
    this.route.params.pipe(takeUntil(this.destroy))
        .subscribe((params: Params) => {
          this.loadData(params['id']);
        });
  }

  ngAfterViewInit() {
    this.backButton!.focus();
  }

  loadData(id?: string) {
    this.editMode = !!id;
    this.isLoading = true;
    this.liveAnnouncer.announce('Loading', 'polite');
    const buildChannelObs =
        id ? this.mttClient.getBuildChannel(id) : observableOf(null);
    const buildChannelProviderObs = this.mttClient.getBuildChannelProviders();
    // Get API call results
    forkJoin([buildChannelObs, buildChannelProviderObs])
        .pipe(first())
        .subscribe(
            ([buildChannelRes, buildChannelProviderRes]) => {
              if (buildChannelRes) {
                this.data = buildChannelRes;
              }
              this.providers =
                  buildChannelProviderRes.build_channel_providers || [];
              this.isLoading = false;
              this.liveAnnouncer.announce('Build channel loaded', 'assertive');
            },
            (error) => {
              this.notifier.showError(
                  `Failed to load build channel '${id}'.`,
                  buildApiErrorMessage(error));
            });
  }

  back() {
    this.location.back();
  }

  /**
   * Get a specific optionDef from a providers' optionDefs
   * @return OptionDef Object, null otherwise
   */
  getOptionDef(optionName: string, providerName: string) {
    const optionDefs = this.getProviderOptionDefs(providerName);
    if (!optionDefs) {
      return null;
    }
    const optionDef = optionDefs.find(o => o.name === optionName);
    return optionDef || null;
  }

  /**
   * Get OptionDefs from a specific provider
   * @return OptionDefs Object, null otherwise
   */
  getProviderOptionDefs(providerName: string) {
    const provider = this.providers.find(p => p.name === providerName);
    return provider && provider.option_defs || null;
  }

  /**
   * Get list of choice from a optionDef
   * @return a list of choice, null otherwise
   */
  getChoices(optionName: string, providerName: string) {
    const optionDef = this.getOptionDef(optionName, providerName);
    return optionDef && optionDef.choices || null;
  }

  /**
   * Check whether a optionDef has non-empty choices array
   * @return boolean
   */
  hasChoices(optionName: string, providerName: string) {
    const optionDef = this.getOptionDef(optionName, providerName);
    if (!optionDef) {
      return false;
    }
    return optionDef.choices && optionDef.choices.length > 0;
  }

  /**
   * When user select a different build channel provider, populate the
   * data.option array with correct value, so that ngModel could bind to the
   * correct value
   */
  onSelectionChange(providerName: string) {
    const options = this.getProviderOptionDefs(providerName) || [];
    this.data.options = options.map(o => ({name: o.name, 'value': ''}));
  }

  /**
   * Validate Form
   * @return boolean. True if form is valid, false otherwise.
   */
  validateForm(): boolean {
    this.invalidInputs = this.getInvalidInputs();
    return !this.invalidInputs.length;
  }

  onSubmit() {
    if (!this.validateForm()) {
      return;
    }
    if (this.editMode) {
      this.mttClient.updateBuildChannel(this.data.id, this.data)
          .pipe(takeUntil(this.destroy))
          .subscribe(
              result => {
                super.resetForm();
                this.back();
                this.notifier.showMessage(
                    `Build channel '${this.data.name}' updated`);
              },
              error => {
                this.notifier.showError(
                    `Failed to update build channel '${this.data.name}'.`,
                    buildApiErrorMessage(error));
              },
          );
    } else {
      this.mttClient.createBuildChannel(this.data)
          .pipe(takeUntil(this.destroy))
          .subscribe(
              result => {
                super.resetForm();
                this.back();
                this.notifier.showMessage(
                    `Build Channel '${this.data.name}' created`);
              },
              error => {
                this.notifier.showError(
                    `Failed to create build channel '${this.data.name}'.`,
                    buildApiErrorMessage(error));
              },
          );
    }
  }
}
