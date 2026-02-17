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

import {SelectionModel} from '@angular/cdk/collections';
import {CdkDragDrop, moveItemInArray} from '@angular/cdk/drag-drop';
import {Component, EventEmitter, Input, OnInit, Output, ChangeDetectionStrategy} from '@angular/core';

import {DeviceAction} from '../services/mtt_models';
import {FormChangeTracker} from '../shared/can_deactivate';
import {assertRequiredInput} from '../shared/util';

/**
 * Device Action Picker
 *
 * The picker is composed of drag and drop area, and a dropdown overlay which
 * will show up if one clicks on the 'add device action' button. It is used to
 * select device actions such as flush, and reboot before a test can be run.
 */
@Component({
  changeDetection: ChangeDetectionStrategy.Eager,standalone: false,
  selector: 'device-action-picker',
  styleUrls: ['device_action_picker.css'],
  templateUrl: './device_action_picker.ng.html',
  providers: [{provide: FormChangeTracker, useExisting: DeviceActionPicker}]
})
export class DeviceActionPicker extends FormChangeTracker implements OnInit {
  @Input() deviceActions!: DeviceAction[];
  @Input() selectedDeviceActions!: DeviceAction[];
  @Output() readonly selectionChange = new EventEmitter();

  selection =
      new SelectionModel<DeviceAction>(true, this.selectedDeviceActions);

  ngOnInit() {
    assertRequiredInput(
        this.deviceActions, 'deviceActions', 'DeviceActionPicker');
    assertRequiredInput(
        this.selectedDeviceActions, 'selectedDeviceActions',
        'DeviceActionPicker');
  }

  // after dropping an dragged item, move the dragged item in place
  drop(event: CdkDragDrop<string[]>) {
    moveItemInArray(
        this.selectedDeviceActions, event.previousIndex, event.currentIndex);
    this.selectionChange.emit();
  }

  // remove an item from drag and drop area, and reset the dropdown menu
  removeItem(item: DeviceAction) {
    const index = this.selectedDeviceActions.indexOf(item);
    if (index > -1) {
      this.selectedDeviceActions.splice(index, 1);
    }
    this.selectionChange.emit();
  }

  // confirm selected device actions in dropdown
  selectActions() {
    this.selectedDeviceActions.push(...this.selection.selected);
    this.selection.clear();
    this.selectionChange.emit();
  }
}
