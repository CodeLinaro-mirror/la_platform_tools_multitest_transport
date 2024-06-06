/**
 * Copyright 2021 Google LLC
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

import {convertToLabHostResource} from '../services/mtt_lab_models';
import {TfcClient} from '../services/tfc_client';
import {getTextContent} from '../testing/jasmine_util';
import {newMockHostResource} from '../testing/mtt_lab_mocks';

import {HostDetailsHostResource} from './host_details_host_resource';
import {HostsModule} from './hosts_module';


describe('HostDetailsHostResource', () => {
  let hostDetailsHostResource: HostDetailsHostResource;
  let hostDetailsHostResourceFixture: ComponentFixture<HostDetailsHostResource>;
  let tfcClient: jasmine.SpyObj<TfcClient>;
  let el: DebugElement;
  const hostname = 'host01';

  beforeEach(() => {
    const hostResource = convertToLabHostResource(
        newMockHostResource(hostname));
    tfcClient = jasmine.createSpyObj('tfcClient', {
      'getHostResource': observableOf(hostResource),
    });

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

    hostDetailsHostResourceFixture =
        TestBed.createComponent(HostDetailsHostResource);
    hostDetailsHostResource = hostDetailsHostResourceFixture.componentInstance;
    hostDetailsHostResource.id = hostname;
    hostDetailsHostResourceFixture.detectChanges();
    el = hostDetailsHostResourceFixture.debugElement;
  });

  afterEach(() => {
    hostDetailsHostResourceFixture.destroy();
  });

  it('should get initialized correctly', () => {
    expect(hostDetailsHostResource).toBeTruthy();
  });

  it('should load host resource correctly', () => {
    hostDetailsHostResource.loadHostResource(hostname);
    expect(tfcClient.getHostResource).toHaveBeenCalledWith(hostname);

    hostDetailsHostResourceFixture.detectChanges();
    expect(getTextContent(el)).toContain('disk_util /tmp');
    expect(getTextContent(el)).toContain('used=10%, free=20%');
  });

  it('should load non-exist host resource correctly', () => {
    hostDetailsHostResource.hostResource = null;
    hostDetailsHostResource.hostResourceNameValueTimes = [];

    hostDetailsHostResourceFixture.detectChanges();
    expect(getTextContent(el)).toContain('No host resource info found.');
  });
});
