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

import {HttpClient} from '@angular/common/http';
import {DebugElement} from '@angular/core';
import {ComponentFixture, TestBed} from '@angular/core/testing';
import {NoopAnimationsModule} from '@angular/platform-browser/animations';
import {RouterModule} from '@angular/router';

import {APP_DATA, AppData} from '../services';
import {newMockAppData} from '../testing/mtt_lab_mocks';

import {AssignedOthersOfflineHostList} from './assigned_others_offline_host_list';
import {HostsModule} from './hosts_module';

describe('AssignedOthersOfflineHostList', () => {
  let assignedOthersOfflineHostList: AssignedOthersOfflineHostList;
  let assignedOthersOfflineHostListFixture:
      ComponentFixture<AssignedOthersOfflineHostList>;
  let mockAppData: AppData;
  let el: DebugElement;

  beforeEach(() => {
    mockAppData = newMockAppData();
    TestBed.configureTestingModule({
      imports: [
        HostsModule,
        NoopAnimationsModule,
        RouterModule,
      ],
      providers: [
        {provide: APP_DATA, useValue: mockAppData},
        {provide: HttpClient},
      ],
    });

    assignedOthersOfflineHostListFixture =
        TestBed.createComponent(AssignedOthersOfflineHostList);
    el = assignedOthersOfflineHostListFixture.debugElement;
    assignedOthersOfflineHostList =
        assignedOthersOfflineHostListFixture.componentInstance;
    assignedOthersOfflineHostListFixture.detectChanges();
  });

  it('initializes a component', () => {
    expect(assignedOthersOfflineHostList).toBeTruthy();
  });
});
