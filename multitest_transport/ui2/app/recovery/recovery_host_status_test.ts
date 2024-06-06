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
import {getTextContent} from 'google3/third_party/py/multitest_transport/ui2/app/testing/jasmine_util';
import {toTitleCase} from 'google3/third_party/py/multitest_transport/ui2/app/testing/mtt_mocks';

import {HostState} from '../services/tfc_models';

import {RecoveryHostStatus} from './recovery_host_status';
import {RecoveryModule} from './recovery_module';

describe('RecoveryHostStatus', () => {
  let recoveryHostStatus: RecoveryHostStatus;
  let recoveryHostStatusFixture: ComponentFixture<RecoveryHostStatus>;
  let el: DebugElement;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [
        NoopAnimationsModule,
        RecoveryModule,
      ],
    });
    recoveryHostStatusFixture = TestBed.createComponent(RecoveryHostStatus);
    el = recoveryHostStatusFixture.debugElement;
    recoveryHostStatus = recoveryHostStatusFixture.componentInstance;
    recoveryHostStatus.state = HostState.RUNNING;
    recoveryHostStatus.ngOnInit();
    recoveryHostStatusFixture.detectChanges();
  });

  it('should get initialized correctly', () => {
    expect(recoveryHostStatus).toBeTruthy();
  });

  it('should display the state of host correctly', () => {
    recoveryHostStatus.ngOnInit();
    expect(getTextContent(el)).toContain(toTitleCase(HostState.RUNNING));
  });
});
