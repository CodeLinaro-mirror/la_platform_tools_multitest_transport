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

import {DeviceInfo} from '../services/tfc_models';
import {getTextContent} from '../testing/jasmine_util';
import {newMockDeviceInfo} from '../testing/mtt_lab_mocks';

import {SharedModule} from './shared_module';
import {StatusButton} from './status_button';

describe('DeviceState', () => {
  let statusButton: StatusButton;
  let statusButtonixture: ComponentFixture<StatusButton>;
  let el: DebugElement;

  let deviceInfo: DeviceInfo;

  beforeEach(() => {
    deviceInfo = newMockDeviceInfo();

    TestBed.configureTestingModule({
      imports: [
        NoopAnimationsModule,
        SharedModule,
      ],
    });

    statusButtonixture = TestBed.createComponent(StatusButton);
    el = statusButtonixture.debugElement;
    statusButton = statusButtonixture.componentInstance;
    statusButton.state = deviceInfo.state;
    statusButton.ngOnInit();
    statusButtonixture.detectChanges();
  });

  it('displays the state', () => {
    expect(getTextContent(el).toLowerCase())
        .toContain(deviceInfo.state.toLowerCase());
  });
});
