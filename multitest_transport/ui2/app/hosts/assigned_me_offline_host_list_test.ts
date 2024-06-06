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

import {APP_DATA, AppData} from '../services';
import {FeedbackService} from '../services/feedback_service';
import {SurveyTrigger} from '../services/mtt_lab_models';
import {TfcClient} from '../services/tfc_client';
import {newMockAppData, newMockLabHostInfosResponse} from '../testing/mtt_lab_mocks';

import {AssignedMeOfflineHostList} from './assigned_me_offline_host_list';
import {HostsModule} from './hosts_module';

describe('AssignedMeOfflineHostList', () => {
  let appDataSpy: AppData;
  let assignedMeOfflineHostList: AssignedMeOfflineHostList;
  let assignedMeOfflineHostListFixture:
      ComponentFixture<AssignedMeOfflineHostList>;
  let el: DebugElement;
  let feedbackService: jasmine.SpyObj<FeedbackService>;
  let tfcClientSpy: jasmine.SpyObj<TfcClient>;

  beforeEach(() => {
    appDataSpy = newMockAppData();
    feedbackService = jasmine.createSpyObj('feedbackService', ['startSurvey']);
    tfcClientSpy =
        jasmine.createSpyObj('tfcClient', {unassignHosts: observableOf()});
    TestBed.configureTestingModule({
      imports: [
        HostsModule,
        NoopAnimationsModule,
        RouterModule,
      ],
      providers: [
        {provide: APP_DATA, useValue: appDataSpy},
        {provide: FeedbackService, useValue: feedbackService},
        {provide: TfcClient, useValue: tfcClientSpy},
      ],
    });
    assignedMeOfflineHostListFixture =
        TestBed.createComponent(AssignedMeOfflineHostList);
    el = assignedMeOfflineHostListFixture.debugElement;
    assignedMeOfflineHostList =
        assignedMeOfflineHostListFixture.componentInstance;
    assignedMeOfflineHostListFixture.detectChanges();
  });

  it('initializes a component', () => {
    expect(assignedMeOfflineHostList).toBeTruthy();
  });

  it('should call HaTS client on batch add devices notes', () => {
    assignedMeOfflineHostList.startBatchAddHostsNotesHats();
    expect(feedbackService.startSurvey)
        .toHaveBeenCalledWith(SurveyTrigger.BATCH_ADD_HOSTS_NOTES);
  });

  it('correctly remove selected Hosts', () => {
    const beforeHosts = newMockLabHostInfosResponse().host_infos!.slice(0, 2);
    const afterHosts = newMockLabHostInfosResponse().host_infos!.slice(1, 2);
    assignedMeOfflineHostList.assignedMeHostListDataSource = beforeHosts;
    assignedMeOfflineHostList.hostListTable.tableRowsSelectManager.selection
        .select(beforeHosts[0].hostname);

    spyOn(assignedMeOfflineHostList.assignedMeHostListDataSourceChange, 'emit');
    spyOn(
        assignedMeOfflineHostList.hostListTable.tableRowsSelectManager,
        'resetSelection');
    spyOn(assignedMeOfflineHostList.hostListTable.matTable, 'renderRows');

    assignedMeOfflineHostList.removeSelectedHosts();
    expect(assignedMeOfflineHostList.hostListTable.tableRowsSelectManager
               .resetSelection)
        .toHaveBeenCalledTimes(1);
    expect(assignedMeOfflineHostList.hostListTable.matTable.renderRows)
        .toHaveBeenCalledTimes(1);
    expect(assignedMeOfflineHostList.assignedMeHostListDataSourceChange.emit)
        .toHaveBeenCalledWith(afterHosts);
    expect(assignedMeOfflineHostList.assignedMeHostListDataSource)
        .toEqual(afterHosts);
  });
});
