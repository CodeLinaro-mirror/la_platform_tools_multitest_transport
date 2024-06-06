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
import {RouterModule} from '@angular/router';
import {of as observableOf} from 'rxjs';

import {TfcClient} from '../services/tfc_client';
import {getTextContent} from '../testing/jasmine_util';
import {newMockLabHostInfo} from '../testing/mtt_lab_mocks';

import {HostDetailsDeviceCountSummaries} from './host_details_device_count_summaries';
import {HostsModule} from './hosts_module';

describe('HostDetailsDeviceCountSummaries', () => {
  let hostDetailsDeviceCountSummaries: HostDetailsDeviceCountSummaries;
  let hostDetailsDeviceCountSummariesFixture:
      ComponentFixture<HostDetailsDeviceCountSummaries>;
  let tfcClient: jasmine.SpyObj<TfcClient>;
  let el: DebugElement;

  const hostname = 'host01';
  const mockHostInfo = newMockLabHostInfo(hostname);

  beforeEach(() => {
    tfcClient = jasmine.createSpyObj('tfcClient', ['getHostInfo']);
    tfcClient.getHostInfo.and.returnValue(observableOf(mockHostInfo));

    TestBed.configureTestingModule({
      imports: [
        HostsModule,
        NoopAnimationsModule,
        RouterModule,
      ],
      providers: [
        {provide: TfcClient, useValue: tfcClient},
      ],
    });

    hostDetailsDeviceCountSummariesFixture =
        TestBed.createComponent(HostDetailsDeviceCountSummaries);
    hostDetailsDeviceCountSummaries =
        hostDetailsDeviceCountSummariesFixture.componentInstance;
    el = hostDetailsDeviceCountSummariesFixture.debugElement;
    hostDetailsDeviceCountSummaries.id = hostname;
    hostDetailsDeviceCountSummariesFixture.detectChanges();
  });

  afterEach(() => {
    hostDetailsDeviceCountSummariesFixture.destroy();
  });

  it('should get initialized correctly', () => {
    expect(hostDetailsDeviceCountSummaries).toBeTruthy();
  });

  it('should call the tfc client api method getHostInfo correctly',
     async () => {
       await hostDetailsDeviceCountSummariesFixture.whenStable();
       expect(tfcClient.getHostInfo).toHaveBeenCalledTimes(1);
     });

  it('correctly displays a given empty list', () => {
    hostDetailsDeviceCountSummaries.data = [];
    hostDetailsDeviceCountSummariesFixture.detectChanges();
    expect(getTextContent(el)).toContain('No device count summaries found.');
  });

  it('correctly displays a given device count summaries list', () => {
    const mockData = mockHostInfo.device_count_summaries;
    hostDetailsDeviceCountSummaries.data = mockData;
    hostDetailsDeviceCountSummariesFixture.detectChanges();
    expect(getTextContent(el)).toContain(mockData[0].run_target);
  });
});
