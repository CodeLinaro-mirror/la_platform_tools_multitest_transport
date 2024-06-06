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

import {DebugElement} from '@angular/core';
import {ComponentFixture, TestBed} from '@angular/core/testing';
import {NoopAnimationsModule} from '@angular/platform-browser/animations';

import {getEl, getEls, getTextContent} from '../testing/jasmine_util';
import {newMockDeviceActionList} from '../testing/mtt_mocks';

import {DeviceActionPicker} from './device_action_picker';
import {DeviceActionsModule} from './device_actions_module';

describe('DeviceActionPicker', () => {
  let deviceActionPicker: DeviceActionPicker;
  let deviceActionPickerFixture: ComponentFixture<DeviceActionPicker>;
  let el: DebugElement;
  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [DeviceActionsModule, NoopAnimationsModule],
    });
    deviceActionPickerFixture = TestBed.createComponent(DeviceActionPicker);
    el = deviceActionPickerFixture.debugElement;
    deviceActionPicker = deviceActionPickerFixture.componentInstance;
    const actions = newMockDeviceActionList();
    deviceActionPicker.deviceActions = actions;
    deviceActionPicker.selectedDeviceActions = [...actions];
    deviceActionPickerFixture.detectChanges();
  });

  it('initializes a component', () => {
    expect(deviceActionPicker).toBeTruthy();
  });

  it('shows HTML correctly', () => {
    const textContent = getTextContent(el);
    expect(textContent).toContain('Add device action');
  });

  it('displays correct number of items', () => {
    const items = getEls(el, '.device-action-item');
    expect(items).toBeTruthy();
    expect(items.length).toBe(3);
  });

  it('deletes item onClick clear icon', () => {
    getEl(el, '.clear-button').click();
    deviceActionPickerFixture.detectChanges();
    expect(deviceActionPicker.selectedDeviceActions.length).toBe(2);
  });

  it('can open the device action menu', () => {
    // no device action menu initially
    expect(getEls(el, '.device-action-menu')).toEqual([]);
    // pressing the add button will open it
    getEl(el, '.add-button').click();
    const textContent = getEl(el, '.device-action-menu').textContent;
    // menu buttons are present
    expect(textContent).toContain('Add device action(s)');
    expect(textContent).toContain('Cancel');
  });
});
