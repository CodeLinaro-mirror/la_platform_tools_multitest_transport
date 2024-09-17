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

import {AfterViewInit, Component, OnInit, QueryList, ViewChild, ViewChildren} from '@angular/core';
import {MatButton} from '@angular/material/button';
import {ActivatedRoute, Router} from '@angular/router';
import {first} from 'rxjs/operators';

import {MttClient} from '../services/mtt_client';
import {BuildChannel, DeviceAction, newDeviceAction, TestResourceType} from '../services/mtt_models';
import {Notifier} from '../services/notifier';
import {FormChangeTracker} from '../shared/can_deactivate';
import {OptionValueChangeEvent} from '../shared/name_multi_value_pair_list_form';
import {buildApiErrorMessage, FormMode} from '../shared/util';

/**
 * Form for creating a device action
 */
@Component({
  selector: 'device-action-edit-page',
  styleUrls: ['device_action_edit_page.css'],
  templateUrl: './device_action_edit_page.ng.html',
})
export class DeviceActionEditPage extends FormChangeTracker implements
    OnInit, AfterViewInit {
  formMode: FormMode = FormMode.NEW;
  data: Partial<DeviceAction> = newDeviceAction();
  buildChannels: BuildChannel[] = [];
  readonly FormMode = FormMode;

  @ViewChild('backButton', {static: false}) backButton?: MatButton;
  @ViewChildren(FormChangeTracker)
  declare trackers: QueryList<FormChangeTracker>;

  constructor(
      private readonly mttClient: MttClient,
      private readonly notifier: Notifier,
      private readonly route: ActivatedRoute, private readonly router: Router) {
    super();
  }

  ngOnInit() {
    this.route.params.pipe(first()).subscribe(params => {
      if (params['id']) {
        this.formMode = FormMode.EDIT;
        this.loadDeviceAction(params['id']);
      }
      if (params['view_id']) {
        this.formMode = FormMode.VIEW;
        this.loadDeviceAction(params['view_id']);
      }
      if (params['copy_id']) {
        this.formMode = FormMode.NEW;
        this.loadDeviceAction(params['copy_id']);
      }
    });
    this.loadBuildChannels();
  }

  canEdit() {
    return this.formMode !== FormMode.VIEW;
  }

  ngAfterViewInit() {
    this.backButton!.focus();
  }

  loadBuildChannels() {
    this.mttClient.getBuildChannels().pipe(first()).subscribe(
        result => {
          this.buildChannels = result.build_channels || [];
        },
        error => {
          this.notifier.showError(
              'Failed to load build channels.', buildApiErrorMessage(error));
        },
    );
  }

  loadDeviceAction(id: string) {
    this.mttClient.getDeviceAction(id).pipe(first()).subscribe(
        result => {
          this.data = result;
          this.data.test_resource_defs = result.test_resource_defs || [];
          this.data.tradefed_target_preparers =
              result.tradefed_target_preparers || [];
          this.data.tradefed_options = result.tradefed_options || [];
          if (this.formMode === FormMode.NEW) {
            // Clear ID to ensure a new device action is created
            delete this.data.id;
            this.data.name = `${this.data.name} (copy)`;
          }
        },
        error => {
          this.notifier.showError(
              `Failed to load device action '${id}'`,
              buildApiErrorMessage(error));
        },
    );
  }

  onAddOption() {
    this.data.tradefed_options!.push({name: '', values: []});
  }

  onRemoveOption(i: number) {
    this.data.tradefed_options!.splice(i, 1);
  }

  onOptionValueChange(event: OptionValueChangeEvent) {
    this.data.tradefed_options![event.index].values = event.value.split('\n');
  }

  onAddTargetPreparer() {
    this.data.tradefed_target_preparers!.push(
        {class_name: '', option_values: []});
  }

  onDeleteTargetPreparer(index: number) {
    this.data.tradefed_target_preparers!.splice(index, 1);
  }

  onAddTestResourceDef() {
    this.data.test_resource_defs!.push({
      name: '',
      test_resource_type: TestResourceType.UNKNOWN,
    });
  }

  onRemoveTestResourceDef(i: number) {
    this.data.test_resource_defs!.splice(i, 1);
  }

  getPageTitle(formMode: FormMode): string {
    switch (formMode) {
      case FormMode.NEW:
        return 'New Device Action';
      case FormMode.EDIT:
        return 'Edit Device Action';
      case FormMode.VIEW:
        return 'View Device Action';
      default:
        return 'Device Action';
    }
  }

  back() {
    this.router.navigate(['/', 'settings', 'device_actions']);
  }

  validate(): boolean {
    this.invalidInputs = this.getInvalidInputs();
    for (const tracker of this.trackers) {
      this.invalidInputs.push(...tracker.getInvalidInputs());
    }
    return !this.invalidInputs.length;
  }

  onSubmit() {
    if (!this.validate()) {
      return;
    }
    const resultDeviceAction: DeviceAction = {...this.data} as DeviceAction;
    if (this.formMode === FormMode.EDIT) {
      this.mttClient
          .updateDeviceAction(resultDeviceAction.id, resultDeviceAction)
          .pipe(first())
          .subscribe(
              () => {
                // Reset form state, because we prevent dirty forms from
                // navigating away
                super.resetForm();
                this.back();
                this.notifier.showMessage(
                    `Device action '${resultDeviceAction.name}' updated`);
              },
              error => {
                this.notifier.showError(
                    `Failed to update device action '${
                        resultDeviceAction.name}'.`,
                    buildApiErrorMessage(error));
              },
          );
    } else if (this.formMode === FormMode.NEW) {
      this.mttClient.createDeviceAction(resultDeviceAction)
          .pipe(first())
          .subscribe(
              () => {
                // Reset form state, because we prevent dirty forms from
                // navigating away
                super.resetForm();
                this.back();
                this.notifier.showMessage(
                    `Device action '${resultDeviceAction.name}' created`);
              },
              error => {
                this.notifier.showError(
                    `Failed to create device action '${
                        resultDeviceAction.name}'.`,
                    buildApiErrorMessage(error));
              },
          );
    }
  }
}
