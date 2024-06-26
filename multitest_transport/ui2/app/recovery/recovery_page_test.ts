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

import {provideHttpClientTesting} from '@angular/common/http/testing';
import {DebugElement} from '@angular/core';
import {ComponentFixture, TestBed} from '@angular/core/testing';
import {NoopAnimationsModule} from '@angular/platform-browser/animations';
import {ActivatedRoute, Router} from '@angular/router';
import {APP_DATA} from 'google3/third_party/py/multitest_transport/ui2/app/services';
import {ActivatedRouteStub} from 'google3/third_party/py/multitest_transport/ui2/app/testing/activated_route_stub';
import {getEl, getEls, getTextContent} from 'google3/third_party/py/multitest_transport/ui2/app/testing/jasmine_util';

import {newMockAppData} from '../testing/mtt_lab_mocks';

import {RecoveryModule} from './recovery_module';
import {RecoveryPage} from './recovery_page';

describe('RecoveryPage', () => {
  const lab = 'Lab 1';
  const runTargets = ['Run Target 1'];
  const hostGroups = ['host group 1', 'host group 2'];
  let el: DebugElement;
  let recoveryPage: RecoveryPage;
  let recoveryPageFixture: ComponentFixture<RecoveryPage>;
  let routerSpy: jasmine.SpyObj<Router>;
  const activatedRouteSpy = new ActivatedRouteStub({
    lab: 'Lab 1',
    hostGroups: ['host group 1', 'host group 2'],
    runTargets: ['Run Target 1'],
  });
  beforeEach(() => {
    routerSpy = jasmine.createSpyObj('Router', ['navigateByUrl']);
    TestBed.configureTestingModule({
      imports: [
        NoopAnimationsModule,
        RecoveryModule,
      ],
      providers: [
        provideHttpClientTesting(),
        {provide: APP_DATA, useValue: newMockAppData()},
        {provide: Router, useValue: routerSpy},
        {
          provide: ActivatedRoute,
          useValue: activatedRouteSpy,
        },
      ],
    });
    recoveryPageFixture = TestBed.createComponent(RecoveryPage);
    recoveryPageFixture.detectChanges();
    el = recoveryPageFixture.debugElement;
    recoveryPage = recoveryPageFixture.componentInstance;
  });

  it('should get initialized correctly', () => {
    const textContent = getTextContent(el);
    expect(textContent).toContain('Recovery');
    expect(recoveryPage).toBeTruthy();
  });

  it('should get params from url correctly', () => {
    expect(recoveryPage.urlParams.lab).toEqual(lab);
    expect(recoveryPage.urlParams.runTargets).toEqual(runTargets);
    expect(recoveryPage.urlParams.hostGroups).toEqual(hostGroups);
  });

  it('should navigate to offline hosts page on return button clicked', () => {
    getEl(el, '#return-button').click();
    expect(routerSpy.navigateByUrl).toHaveBeenCalledTimes(1);
    expect(routerSpy.navigateByUrl).toHaveBeenCalledWith('/offline_hosts');
  });

  it('on hide device list should set hostName to empty string ', () => {
    recoveryPage.focusedHostName = 'host1';
    recoveryPage.unfocusHost();
    expect(recoveryPage.focusedHostName).toBe('');
  });

  it('should show or hide device list panel then focus host name changed',
     () => {
       let recoveryDevice: HTMLElement[] = [];

       // show device list panel
       recoveryPage.focusedHostName = 'host1';
       recoveryPageFixture.detectChanges();
       recoveryDevice = getEls(el, '.recovery-device');
       expect(recoveryDevice.length).toBe(1);

       // hide device list panel
       recoveryPage.focusedHostName = '';
       recoveryPageFixture.detectChanges();
       recoveryDevice = getEls(el, '.recovery-device');
       expect(recoveryDevice.length).toBe(0);
     });
});
