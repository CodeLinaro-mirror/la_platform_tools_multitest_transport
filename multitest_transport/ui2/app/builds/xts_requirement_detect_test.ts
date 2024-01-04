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
import {MAT_DIALOG_DATA, MatDialogRef} from '@angular/material/dialog';
import {NoopAnimationsModule} from '@angular/platform-browser/animations';
import {RouterTestingModule} from '@angular/router/testing';
import {of as observableOf} from 'rxjs';

import {APP_DATA} from '../services';
import {MttClient} from '../services/mtt_client';
import {Notifier} from '../services/notifier';
import {getTextContent} from '../testing/jasmine_util';
import {newMockAppData} from '../testing/mtt_lab_mocks';
import {newMockTest} from '../testing/mtt_mocks';

import {BuildsModule} from './builds_module';
import {XtsRequirementDetect, XtsRequirementDetectData} from './xts_requirement_detect';

describe('XtsRequirementDetect', () => {
  const test = newMockTest('testId', 'testName');
  const appData = newMockAppData();
  const dialogData: XtsRequirementDetectData = {
    testRunConfig: {
      test_id: 'testId',
      device_specs: [],
    },
  };

  let dialogRef: jasmine.SpyObj<MatDialogRef<XtsRequirementDetect>>;
  let mttClient: jasmine.SpyObj<MttClient>;
  let notifier: jasmine.SpyObj<Notifier>;

  let fixture: ComponentFixture<XtsRequirementDetect>;
  let component: XtsRequirementDetect;
  let el: DebugElement;

  beforeEach(() => {
    mttClient =
        jasmine.createSpyObj('mttClient', ['getTest', 'getBuildChannels']);
    mttClient.getTest.and.returnValue(observableOf(test));
    mttClient.getBuildChannels.and.returnValue(
        observableOf({build_channels: []}));
    notifier = jasmine.createSpyObj(['confirm', 'showError']);
    dialogRef = jasmine.createSpyObj<MatDialogRef<XtsRequirementDetect>>(
        ['close', 'backdropClick']);
    dialogRef.backdropClick.and.returnValue(observableOf());

    TestBed.configureTestingModule({
      imports: [BuildsModule, NoopAnimationsModule, RouterTestingModule],
      providers: [
        {provide: APP_DATA, useValue: appData},
        {provide: MAT_DIALOG_DATA, useFactory: () => dialogData},
        {provide: MatDialogRef, useValue: dialogRef},
        {provide: MttClient, useValue: mttClient},
        {provide: Notifier, useValue: notifier},
      ],
    });

    fixture = TestBed.createComponent(XtsRequirementDetect);
    fixture.detectChanges();
    el = fixture.debugElement;
    component = fixture.componentInstance;
  });

  it('initializes a component', () => {
    expect(component).toBeTruthy();
  });

  it('calls APIs correctly', () => {
    expect(mttClient.getTest).toHaveBeenCalled();
    expect(mttClient.getBuildChannels).toHaveBeenCalled();
  });

  it('shows HTML correctly', () => {
    const textContent = getTextContent(el);
    expect(textContent).toContain('Detect xTS Requirements');
    expect(textContent).toContain('Select Devices');
    expect(textContent).toContain('Set Resources');
  });

  it('should create new test run config correctly on submit', () => {
    spyOn(component.configSubmitted, 'emit');
    component.submit();
    expect(component.configSubmitted.emit).toHaveBeenCalled();
    expect(dialogRef.close).toHaveBeenCalled();
  });
});
