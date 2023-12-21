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

import {LiveAnnouncer} from '@angular/cdk/a11y';
import {DebugElement} from '@angular/core';
import {ComponentFixture, TestBed} from '@angular/core/testing';
import {NoopAnimationsModule} from '@angular/platform-browser/animations';
import {RouterTestingModule} from '@angular/router/testing';
import {of as observableOf} from 'rxjs';

import {BuildClient, MttClient} from '../services/mtt_client';
import * as mttModels from '../services/mtt_models';
import {getTextContent} from '../testing/jasmine_util';
import {newMockBuild} from '../testing/mtt_mocks';

import {BuildDetail} from './build_detail';
import {BuildsModule} from './builds_module';

describe('BuildDetail', () => {
  const build: mttModels.Build = newMockBuild(
      'build_id_1', 'name_1', 'file:///file/path_1', ['label_1', 'label_2']);

  let buildDetail: BuildDetail;
  let buildDetailFixture: ComponentFixture<BuildDetail>;
  let liveAnnouncer: jasmine.SpyObj<LiveAnnouncer>;
  let buildClient: jasmine.SpyObj<BuildClient>;

  let el: DebugElement;

  beforeEach(() => {
    liveAnnouncer = jasmine.createSpyObj('liveAnnouncer', ['announce']);
    buildClient = jasmine.createSpyObj('buildClient', ['get']);
    buildClient.get.and.returnValue(observableOf(build));

    TestBed.configureTestingModule({
      imports: [BuildsModule, NoopAnimationsModule, RouterTestingModule],
      providers: [
        {provide: LiveAnnouncer, useValue: liveAnnouncer},
        {provide: MttClient, useValue: {builds: buildClient}},
      ],
    });

    buildDetailFixture = TestBed.createComponent(BuildDetail);
    el = buildDetailFixture.debugElement;
    buildDetail = buildDetailFixture.componentInstance;
    buildDetail.buildId = build.id!;
    buildDetailFixture.detectChanges();
  });

  it('gets initialized', () => {
    expect(buildDetail).toBeTruthy();
  });

  it('calls the build client api method get', () => {
    expect(liveAnnouncer.announce).toHaveBeenCalledWith('Loading', 'polite');
    expect(buildClient.get).toHaveBeenCalled();
  });

  it('displays the correct build data', () => {
    const textContent = getTextContent(el);
    expect(textContent).toContain(build.id!);
    // TODO: Add more checks as page is built.
  });
});
