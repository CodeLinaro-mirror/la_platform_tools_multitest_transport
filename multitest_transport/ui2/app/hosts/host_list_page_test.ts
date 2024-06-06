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
import {Title} from '@angular/platform-browser';
import {NoopAnimationsModule} from '@angular/platform-browser/animations';
import {provideRouter} from '@angular/router';
import {of as observableOf} from 'rxjs';

import {APP_DATA} from '../services';
import {TfcClient} from '../services/tfc_client';
import {LAB_APPLICATION_NAME} from '../shared/shared_module';
import {newMockAppData} from '../testing/mtt_lab_mocks';

import {HostListPage} from './host_list_page';
import {HostsModule} from './hosts_module';

describe('HostListPage', () => {
  let hostListPage: HostListPage;
  let hostListPageFixture: ComponentFixture<HostListPage>;
  let el: DebugElement;
  let tfcClient: jasmine.SpyObj<TfcClient>;

  beforeEach(() => {
    tfcClient = jasmine.createSpyObj('tfcClient', {
      getHostInfos: observableOf({}),
      getFilterHintList: observableOf({}),
      getLabInfo: observableOf({}),
    });

    TestBed.configureTestingModule({
      declarations: [],
      imports: [
        HostsModule,
        NoopAnimationsModule,
      ],
      providers: [
        Title,
        provideRouter([]),
        {provide: APP_DATA, useValue: newMockAppData()},
        {provide: TfcClient, useValue: tfcClient},
      ],
    });
    hostListPageFixture = TestBed.createComponent(HostListPage);
    el = hostListPageFixture.debugElement;
    hostListPage = hostListPageFixture.componentInstance;
    hostListPageFixture.detectChanges();
  });

  it('initializes correctly and has a correct page title', () => {
    expect(hostListPage).toBeTruthy();
    expect(el.injector.get(Title).getTitle())
        .toEqual(`${LAB_APPLICATION_NAME} - Hosts`);
  });
});
