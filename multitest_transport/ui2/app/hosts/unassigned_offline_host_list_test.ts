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
import {ComponentFixture, TestBed} from '@angular/core/testing';
import {NoopAnimationsModule} from '@angular/platform-browser/animations';
import {RouterModule} from '@angular/router';

import {APP_DATA} from '../services';
import {FeedbackService} from '../services/feedback_service';
import {SurveyTrigger} from '../services/mtt_lab_models';
import {newMockAppData} from '../testing/mtt_lab_mocks';

import {HostsModule} from './hosts_module';
import {UnassignedOfflineHostList} from './unassigned_offline_host_list';

describe('UnassignedOfflineHostList', () => {
  let feedbackService: jasmine.SpyObj<FeedbackService>;
  let unassignedOfflineHostList: UnassignedOfflineHostList;
  let unassignedOfflineHostListFixture:
      ComponentFixture<UnassignedOfflineHostList>;

  beforeEach(() => {
    feedbackService = jasmine.createSpyObj('feedbackService', ['startSurvey']);
    TestBed.configureTestingModule({
      imports: [
        HostsModule,
        NoopAnimationsModule,
        RouterModule,
      ],
      providers: [
        {provide: APP_DATA, useValue: newMockAppData()},
        {provide: FeedbackService, useValue: feedbackService},
        {provide: HttpClient},
      ],
    });

    unassignedOfflineHostListFixture =
        TestBed.createComponent(UnassignedOfflineHostList);
    unassignedOfflineHostList =
        unassignedOfflineHostListFixture.componentInstance;
    unassignedOfflineHostListFixture.detectChanges();
  });

  it('initializes a component', () => {
    expect(unassignedOfflineHostList).toBeTruthy();
  });

  it('should call HaTS client on batch add devices notes', () => {
    unassignedOfflineHostList.startBatchAddHostsNotesHats();
    expect(feedbackService.startSurvey)
        .toHaveBeenCalledWith(SurveyTrigger.BATCH_ADD_HOSTS_NOTES);
  });
});
