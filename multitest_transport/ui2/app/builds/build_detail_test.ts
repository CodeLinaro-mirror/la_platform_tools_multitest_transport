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
import {ComponentFixture, inject, TestBed} from '@angular/core/testing';
import {MatDialog} from '@angular/material/dialog';
import {NoopAnimationsModule} from '@angular/platform-browser/animations';
import {RouterTestingModule} from '@angular/router/testing';
import {of as observableOf} from 'rxjs';

import {APP_DATA} from '../services';
import {BuildClient, MttClient} from '../services/mtt_client';
import * as mttModels from '../services/mtt_models';
import {getEl, getTextContent} from '../testing/jasmine_util';
import {newMockAppData} from '../testing/mtt_lab_mocks';
import {newMockBuild} from '../testing/mtt_mocks';

import {BuildDetail} from './build_detail';
import {BuildEditor} from './build_editor';
import {BuildsModule} from './builds_module';
import {XtsRequirementDetect} from './xts_requirement_detect';

describe('BuildDetail', () => {
  const build: mttModels.Build = newMockBuild();
  const appData = newMockAppData();

  let buildDetail: BuildDetail;
  let buildDetailFixture: ComponentFixture<BuildDetail>;
  let liveAnnouncer: jasmine.SpyObj<LiveAnnouncer>;
  let buildClient: jasmine.SpyObj<BuildClient>;

  let el: DebugElement;

  beforeEach(() => {
    liveAnnouncer =
        jasmine.createSpyObj('liveAnnouncer', ['announce', 'clear']);
    buildClient = jasmine.createSpyObj('buildClient', ['get']);
    buildClient.get.and.returnValue(observableOf(build));

    TestBed.configureTestingModule({
      imports: [BuildsModule, NoopAnimationsModule, RouterTestingModule],
      providers: [
        {provide: APP_DATA, useValue: appData},
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
    expect(textContent).toContain('Metadata');
    expect(textContent).toContain(build.name);
    expect(textContent).toContain(build.file_url);
    expect(textContent).toContain(build.labels.join(','));
    expect(textContent).toContain('xTS Testing Requirements');
    expect(textContent)
        .toContain(build.xts_requirements!.detection_test_run_id);
  });

  it('should open xts requirement detect dialog when clicking detect button',
     inject([MatDialog], (dialog: MatDialog) => {
       spyOn(dialog, 'open').and.callThrough();

       getEl(el, '.detect-button').click();
       expect(dialog.open).toHaveBeenCalledTimes(1);

       const dialogParams = {
         width: '80vw',
         height: '80vh',
         panelClass: 'xts-requirements-detect-dialog',
         data: {testRunConfig: mttModels.initXtsRequirementDetect()},
       };
       expect(dialog.open)
           .toHaveBeenCalledWith(XtsRequirementDetect, dialogParams);
     }));

  it('should open build editor dialog when clicking update button',
     inject([MatDialog], (dialog: MatDialog) => {
       spyOn(dialog, 'open').and.callThrough();

       getEl(el, '.update-button').click();
       expect(dialog.open).toHaveBeenCalledTimes(1);

       const dialogParams = {
         width: '1000px',
         height: '440px',
         panelClass: 'build-editor',
         data: {
           build: {
             name: build.name,
             file_url: build.file_url,
             size: build.size,
             labels: build.labels,
           }
         },
       };
       expect(dialog.open).toHaveBeenCalledWith(BuildEditor, dialogParams);
     }));
});
