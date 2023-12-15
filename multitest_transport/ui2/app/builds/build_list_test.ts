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

import {DebugElement} from '@angular/core';
import {ComponentFixture, TestBed} from '@angular/core/testing';
import {NoopAnimationsModule} from '@angular/platform-browser/animations';
import {RouterTestingModule} from '@angular/router/testing';
import {of as observableOf} from 'rxjs';

import {BuildClient, MttClient} from '../services/mtt_client';
import {Notifier} from '../services/notifier';
import {getTextContent} from '../testing/jasmine_util';
import {newMockBuild} from '../testing/mtt_mocks';

import {BuildList} from './build_list';
import {BuildsModule} from './builds_module';

describe('BuildList', () => {
  const BUILDS = {
    builds: [
      newMockBuild(
          'build_id_1', 'name_1', 'file:///file/path_1',
          ['label_1', 'label_2']),
      newMockBuild(
          'build_id_2', 'name_2', 'file:///file/path_2', ['label_3', 'label_4'])
    ],
  };

  let buildList: BuildList;
  let buildListFixture: ComponentFixture<BuildList>;
  let buildClient: jasmine.SpyObj<BuildClient>;
  let notifier: jasmine.SpyObj<Notifier>;
  let el: DebugElement;

  beforeEach(() => {
    buildClient = jasmine.createSpyObj('buildClient', ['list']);
    buildClient.list.and.returnValue(observableOf(BUILDS));

    notifier = jasmine.createSpyObj(['confirm', 'showError']);

    TestBed.configureTestingModule({
      imports: [BuildsModule, NoopAnimationsModule, RouterTestingModule],
      providers: [
        {provide: MttClient, useValue: {builds: buildClient}},
        {provide: Notifier, useValue: notifier},
      ],
    });

    buildListFixture = TestBed.createComponent(BuildList);
    buildListFixture.detectChanges();
    el = buildListFixture.debugElement;
    buildList = buildListFixture.componentInstance;
  });

  it('gets initialized', () => {
    expect(buildList).toBeTruthy();
  });

  it('calls the build client api method list', () => {
    expect(buildClient.list).toHaveBeenCalled();
  });

  it('should display builds correctly', () => {
    const textContent = getTextContent(el);
    for (const build of BUILDS.builds) {
      expect(textContent).toContain(build.name);
      expect(textContent).toContain(build.file_url);
    }
  });
});
