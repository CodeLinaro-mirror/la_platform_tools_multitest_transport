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

import {DebugElement} from '@angular/core';
import {ComponentFixture, TestBed} from '@angular/core/testing';
import {NoopAnimationsModule} from '@angular/platform-browser/animations';
import {provideRouter} from '@angular/router';
import {of as observableOf} from 'rxjs';

import {ConfigSetClient, MttClient} from '../services/mtt_client';
import {ConfigSetInfo, ConfigSetStatus} from '../services/mtt_models';
import {getTextContent} from '../testing/jasmine_util';
import * as testUtil from '../testing/mtt_mocks';

import {ConfigSetList} from './config_set_list';
import {ConfigSetsModule} from './config_sets_module';


describe('ConfigSetList', () => {
  let configSetList: ConfigSetList;
  let configSetListFixture: ComponentFixture<ConfigSetList>;
  let mttClient: jasmine.SpyObj<MttClient>;
  let configSetClient: jasmine.SpyObj<ConfigSetClient>;
  let el: DebugElement;

  let imported: ConfigSetInfo;
  let notImported: ConfigSetInfo;
  let updatable: ConfigSetInfo;

  beforeEach(() => {
    imported = testUtil.newMockImportedConfigSetInfo();
    notImported = testUtil.newMockNotImportedConfigSetInfo();
    updatable = testUtil.newMockImportedConfigSetInfo();
    updatable.status = ConfigSetStatus.UPDATABLE;

    configSetClient =
        jasmine.createSpyObj('configSetClient', ['getLatestVersion']);
    configSetClient.getLatestVersion.and.returnValue(observableOf());
    mttClient = {
      ...jasmine.createSpyObj(
          'mttClient', ['getBuildChannels', 'getConfigSetInfos']),
      configSets: configSetClient,
    };
    mttClient.getConfigSetInfos.and.returnValue(
        observableOf({config_set_infos: []}));

    TestBed.configureTestingModule({
      imports: [ConfigSetsModule, NoopAnimationsModule],
      providers: [
        provideRouter([]),
        {provide: MttClient, useValue: mttClient},
      ],
    });

    configSetListFixture = TestBed.createComponent(ConfigSetList);
    el = configSetListFixture.debugElement;
    configSetListFixture.detectChanges();
    configSetList = configSetListFixture.componentInstance;

    reload([], notImported);
  });

  function reload(configSetInfos: ConfigSetInfo[], updatedInfo: ConfigSetInfo) {
    mttClient.getConfigSetInfos.and.returnValue(
        observableOf({config_set_infos: configSetInfos}));
    configSetClient.getLatestVersion.and.returnValue(observableOf(updatedInfo));
    configSetList.load();
    configSetListFixture.detectChanges();
  }

  it('initializes a component', () => {
    expect(configSetList).toBeTruthy();
    expect(getTextContent(el)).toContain('Import');
    expect(getTextContent(el)).toContain('Upload');
  });

  it('lists imported configs', () => {
    reload([imported], imported);
    const text = getTextContent(el);
    expect(text).toContain(imported.name);
    expect(text).not.toContain(notImported.name);
  });

  it('checks for updates', () => {
    reload([imported, updatable], updatable);
    const text = getTextContent(el);
    expect(text).toContain(updatable.name);
    expect(text).toContain('Update');
  });
});
