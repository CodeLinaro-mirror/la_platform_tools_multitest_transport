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

import {ComponentFixture, TestBed} from '@angular/core/testing';
import {NoopAnimationsModule} from '@angular/platform-browser/animations';
import {provideRouter} from '@angular/router';
import {of as observableOf} from 'rxjs';

import {MttClient} from '../services/mtt_client';

import {SettingPage} from './setting_page';
import {SettingsModule} from './settings_module';

describe('SettingPage', () => {
  let settingPage: SettingPage;
  let settingPageFixture: ComponentFixture<SettingPage>;
  let mttClient: jasmine.SpyObj<MttClient>;

  beforeEach(() => {
    mttClient = jasmine.createSpyObj(
        'mttClient',
        ['getBuildChannels', 'getNodeConfig', 'getDeviceActionList']);
    mttClient.getBuildChannels.and.returnValue(
        observableOf({build_channels: []}));
    mttClient.getNodeConfig.and.returnValue(observableOf({}));
    mttClient.getDeviceActionList.and.returnValue(
        observableOf({device_actions: []}));
    TestBed.configureTestingModule({
      imports: [NoopAnimationsModule, SettingsModule],
      providers: [
        provideRouter([]),
        {provide: MttClient, useValue: mttClient},
      ],
    });
    settingPageFixture = TestBed.createComponent(SettingPage);
    settingPage = settingPageFixture.componentInstance;
    settingPageFixture.detectChanges();
  });

  it('initializes a component', () => {
    expect(settingPage).toBeTruthy();
  });
});
