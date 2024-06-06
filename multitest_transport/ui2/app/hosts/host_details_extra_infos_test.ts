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

import {DebugElement, SimpleChange} from '@angular/core';
import {ComponentFixture, TestBed} from '@angular/core/testing';
import {NoopAnimationsModule} from '@angular/platform-browser/animations';
import {RouterModule} from '@angular/router';

import {getTextContent} from '../testing/jasmine_util';
import {newMockLabHostExtraInfo} from '../testing/mtt_lab_mocks';

import {HostDetailsExtraInfos} from './host_details_extra_infos';
import {HostsModule} from './hosts_module';


describe('HostDetailsExtraInfos', () => {
  let hostDetailsExtraInfos: HostDetailsExtraInfos;
  let hostDetailsExtraInfosFixture: ComponentFixture<HostDetailsExtraInfos>;
  let el: DebugElement;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [
        HostsModule,
        NoopAnimationsModule,
        RouterModule,
      ],
    });

    hostDetailsExtraInfosFixture =
        TestBed.createComponent(HostDetailsExtraInfos);
    hostDetailsExtraInfos = hostDetailsExtraInfosFixture.componentInstance;
    hostDetailsExtraInfos.extraInfo = newMockLabHostExtraInfo(0);
    hostDetailsExtraInfos.extraInfoList = (
        hostDetailsExtraInfos.extraInfoToExtraInfoList(
            hostDetailsExtraInfos.extraInfo));
    hostDetailsExtraInfosFixture.detectChanges();
    el = hostDetailsExtraInfosFixture.debugElement;
  });

  afterEach(() => {
    hostDetailsExtraInfosFixture.destroy();
  });

  it('should get initialized correctly', () => {
    expect(hostDetailsExtraInfos).toBeTruthy();
  });

  it('correctly displays a given extra infos', () => {
    const expectedIp = '127.0.0.1';
    hostDetailsExtraInfos.extraInfo = newMockLabHostExtraInfo(0);
    hostDetailsExtraInfos.extraInfo['ip'] = expectedIp;
    hostDetailsExtraInfos.extraInfoList = (
        hostDetailsExtraInfos.extraInfoToExtraInfoList(
            hostDetailsExtraInfos.extraInfo));
    hostDetailsExtraInfosFixture.detectChanges();
    let ip = null;
    for (const entry of hostDetailsExtraInfos.extraInfoList) {
      if (entry.key === 'ip') {
        ip = entry.value;
      }
    }
    expect(ip).toEqual(expectedIp);
    expect(getTextContent(el)).toContain(expectedIp);
  });

  it('set new values correctly when params changed', () => {
    const hostIp = '127.0.0.1';
    const wifi = 'abc-123';
    hostDetailsExtraInfos.extraInfo = newMockLabHostExtraInfo(0);
    hostDetailsExtraInfos.extraInfo['hostIp'] = hostIp;
    hostDetailsExtraInfos.extraInfoList = (
        hostDetailsExtraInfos.extraInfoToExtraInfoList(
            hostDetailsExtraInfos.extraInfo));

    hostDetailsExtraInfosFixture.detectChanges();
    expect(getTextContent(el)).toContain(hostIp);

    hostDetailsExtraInfos.ngOnChanges(
        {extraInfo: new SimpleChange(null, {hostIp, wifi}, false)});
    hostDetailsExtraInfosFixture.detectChanges();
    expect(hostDetailsExtraInfos.extraInfo['hostIp']).toEqual(hostIp);
    expect(hostDetailsExtraInfos.extraInfo['wifi']).toEqual(wifi);
  });
});
