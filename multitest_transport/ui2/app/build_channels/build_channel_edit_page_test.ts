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
import {ComponentFixture, TestBed} from '@angular/core/testing';
import {NoopAnimationsModule} from '@angular/platform-browser/animations';
import {ActivatedRoute, RouterModule} from '@angular/router';
import {of as observableOf} from 'rxjs';

import {MttClient} from '../services/mtt_client';
import {newMockBuildChannelConfig, newMockBuildChannelProviderList} from '../testing/mtt_mocks';

import {BuildChannelEditPage} from './build_channel_edit_page';
import {BuildChannelsModule} from './build_channels_module';

describe('BuildChannelEditPage', () => {
  const BUILD_CHANNEL_CONFIG = newMockBuildChannelConfig();

  const BUILD_CHANNEL_PROVIDERS = newMockBuildChannelProviderList();
  const GOOGLE_CLOUD_STORAGE_PROVIDER = 'Google Cloud Storage';

  let buildChannelEditPage: BuildChannelEditPage;
  let buildChannelEditPageFixture: ComponentFixture<BuildChannelEditPage>;
  let mttClient: jasmine.SpyObj<MttClient>;
  let liveAnnouncer: jasmine.SpyObj<LiveAnnouncer>;

  beforeEach(() => {
    liveAnnouncer =
        jasmine.createSpyObj('liveAnnouncer', ['announce', 'clear']);
    mttClient = jasmine.createSpyObj(
        'mttClient', ['getBuildChannel', 'getBuildChannelProviders']);
    mttClient.getBuildChannel.and.returnValue(
        observableOf(BUILD_CHANNEL_CONFIG));
    mttClient.getBuildChannelProviders.and.returnValue(
        observableOf({build_channel_providers: [...BUILD_CHANNEL_PROVIDERS]}));

    TestBed.configureTestingModule({
      imports: [BuildChannelsModule, NoopAnimationsModule, RouterModule],
      providers: [
        {provide: MttClient, useValue: mttClient},
        {
          provide: ActivatedRoute,
          useValue: {params: observableOf({'id': '123'})},
        },
        {provide: LiveAnnouncer, useValue: liveAnnouncer},
      ],
    });

    buildChannelEditPageFixture = TestBed.createComponent(BuildChannelEditPage);
    buildChannelEditPageFixture.detectChanges();
    buildChannelEditPage = buildChannelEditPageFixture.componentInstance;
  });

  it('gets initialized correctly', () => {
    expect(buildChannelEditPage).toBeTruthy();
  });

  it('calls API correctly', () => {
    expect(mttClient.getBuildChannelProviders).toHaveBeenCalled();
  });

  it('loads build channel data correctly', () => {
    expect(mttClient.getBuildChannel).toHaveBeenCalled();
    expect(buildChannelEditPage.data.id).toBe(BUILD_CHANNEL_CONFIG.id);
    expect(buildChannelEditPage.data.name).toBe(BUILD_CHANNEL_CONFIG.name);
    expect(buildChannelEditPage.data.provider_name)
        .toBe(BUILD_CHANNEL_CONFIG.provider_name);
  });

  it('displays and announces a loading mask', () => {
    expect(liveAnnouncer.announce).toHaveBeenCalledWith('Loading', 'polite');
    expect(liveAnnouncer.announce)
        .toHaveBeenCalledWith('Build channel loaded', 'assertive');
  });

  describe('getProviderOptionDefs', () => {
    it('return null on incorrect value', () => {
      const res =
          buildChannelEditPage.getProviderOptionDefs('random_provider_name');
      expect(res).toBe(null);
    });

    it('return correct value on valid input', () => {
      const res = buildChannelEditPage.getProviderOptionDefs(
          GOOGLE_CLOUD_STORAGE_PROVIDER);
      expect(res![0].name).toBe('bucket_name');
    });
  });

  describe('getOptionDef', () => {
    it('return null on incorrect value', () => {
      const res = buildChannelEditPage.getOptionDef(
          'random_option_def_name', 'random_provider_name');
      expect(res).toBe(null);
    });

    it('return correct value on valid input', () => {
      const res = buildChannelEditPage.getOptionDef(
          'bucket_name', 'Google Cloud Storage');
      expect(res!.name).toBe('bucket_name');
      expect(res!.choices!.length).toBe(0);
      expect(res!.value_type).toBe('str');
    });
  });

  describe('getChoices', () => {
    it('return null on incorrect value', () => {
      const res = buildChannelEditPage.getChoices(
          'random_option_def_name', 'random_provider_name');
      expect(res).toBe(null);
    });

    it('return correct value on valid input', () => {
      const choices = buildChannelEditPage.getChoices(
          'bucket_name', 'Google Cloud Storage');
      expect(choices!.length).toBe(0);
    });

    it('return null if provider does not support choices', () => {
      const choices = buildChannelEditPage.getChoices('bucket_name', 'Android');
      expect(choices).toBe(null);
    });
  });

  describe('hasChoices', () => {
    it('return false on incorrect value', () => {
      const res = buildChannelEditPage.hasChoices(
          'random_option_def_name', 'random_provider_name');
      expect(res).toBe(false);
    });

    it('return correct value on valid input', () => {
      let res = buildChannelEditPage.hasChoices(
          'bucket_name', 'Google Cloud Storage');
      expect(res).toBe(false);
      res = buildChannelEditPage.hasChoices('test_name', 'Test Storage');
      expect(res).toBe(false);
    });
  });
});
