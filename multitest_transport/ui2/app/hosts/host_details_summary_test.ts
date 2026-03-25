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
import {ActivatedRoute, RouterModule} from '@angular/router';
import {of as observableOf} from 'rxjs';

import {APP_DATA} from '../services/app_data';
import {TfcClient} from '../services/tfc_client';
import {getTextContent} from '../testing/jasmine_util';
import {newMockAppData, newMockLabHostInfo} from '../testing/mtt_lab_mocks';

import {HostDetailsSummary} from './host_details_summary';
import {HostsModule} from './hosts_module';

describe('HostDetailsSummary', () => {
  let hostDetailsSummary: HostDetailsSummary;
  let hostDetailsSummaryFixture: ComponentFixture<HostDetailsSummary>;
  let tfcClient: jasmine.SpyObj<TfcClient>;
  let hostInfoSpy: jasmine.Spy;

  let el: DebugElement;

  const hostname = 'host01';

  beforeEach(() => {
    tfcClient = jasmine.createSpyObj('tfcClient', ['getHostInfo']);
    hostInfoSpy = tfcClient.getHostInfo.and.returnValue(
      observableOf(newMockLabHostInfo(hostname)),
    );

    TestBed.configureTestingModule({
      imports: [HostsModule, NoopAnimationsModule, RouterModule],
      providers: [
        {provide: APP_DATA, useValue: newMockAppData()},
        {provide: TfcClient, useValue: tfcClient},
        {
          provide: ActivatedRoute,
          useValue: {params: observableOf({id: hostname})},
        },
      ],
    });

    hostDetailsSummaryFixture = TestBed.createComponent(HostDetailsSummary);
    el = hostDetailsSummaryFixture.debugElement;
    hostDetailsSummary = hostDetailsSummaryFixture.componentInstance;
    hostDetailsSummary.id = hostname;
    hostDetailsSummaryFixture.detectChanges();
  });

  afterEach(() => {
    hostDetailsSummaryFixture.destroy();
  });

  it('should get initialized correctly', () => {
    const textContent = getTextContent(el);
    expect(hostDetailsSummary).toBeTruthy();
    expect(textContent).toContain('Test Harness Version');
  });

  it('should call the tfc client api method getHostInfo correctly', async () => {
    await hostDetailsSummaryFixture.whenStable();
    expect(tfcClient.getHostInfo).toHaveBeenCalledTimes(1);
  });
});
