/**
 * Copyright 2019 Google LLC
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

import {Location} from '@angular/common';
import {DebugElement} from '@angular/core';
import {ComponentFixture, TestBed, fakeAsync, tick} from '@angular/core/testing';
import {Event, NavigationEnd, Router, RouterModule} from '@angular/router';
import {of as observableOf, Subject} from 'rxjs';

import {Mtt, MttModule} from './app';
import {AnalyticsService} from './services/analytics_service';
import {APP_DATA} from './services/app_data';
import {CommonParamsService} from './services/common_params_service';
import {NavigationEventService, NavigationTarget} from './services/navigation_event_service';
import {UserService} from './services/user_service';
import {HeaderSlotService} from './shared/header_slot_service';
import {getEl} from './testing/jasmine_util';

describe('Mtt', () => {
  let mtt: Mtt;
  let mttFixture: ComponentFixture<Mtt>;
  let el: DebugElement;
  let analyticsServiceSpy: jasmine.SpyObj<AnalyticsService>;
  let userServiceSpy: jasmine.SpyObj<UserService>;
  let commonParams: Record<string, string>;
  // Mutable so that tests can flip the Lab Console feature flags.
  let appData: {
    netdataUrl: string,
    enableLabConsoleSearchPage?: boolean,
    enableLabConsoleUI?: boolean,
  };

  beforeEach(() => {
    commonParams = {};
    appData = {netdataUrl: 'localhost:8008'};
    analyticsServiceSpy = jasmine.createSpyObj(['trackLocation']);
    userServiceSpy = jasmine.createSpyObj('userService', {
      checkPermission: observableOf(true),
      setAdmin: undefined,
    });

    TestBed.configureTestingModule({
      imports: [MttModule, RouterModule],
      providers: [
        {provide: APP_DATA, useValue: appData},
        {provide: AnalyticsService, useValue: analyticsServiceSpy},
        {provide: UserService, useValue: userServiceSpy},
        {
          provide: CommonParamsService,
          useValue: {getCommonParams: () => commonParams},
        },
      ],
    });

    mttFixture = TestBed.createComponent(Mtt);
    el = mttFixture.debugElement;
    mttFixture.detectChanges();
    mtt = mttFixture.componentInstance;
  });

  it('should gets initialized correctly', () => {
    expect(mtt).toBeTruthy();
  });

  it('should reverse sideNavExpanded on toggleSidenavButton click', () => {
    const sideNavExpanded = mtt.sideNavExpanded;
    getEl(el, '.toggleSidenavButton').click();
    expect(mtt.sideNavExpanded).not.toEqual(sideNavExpanded);
  });

  it('calls checkPermission correctly', () => {
    expect(userServiceSpy.checkPermission).toHaveBeenCalledTimes(1);
  });

  it('should track a page view when monitor button is clicked', () => {
    getEl(el, '#monitorButton').click();
    expect(analyticsServiceSpy.trackLocation).toHaveBeenCalledWith('netdata');
  });

  it('should redirect empty path to /test_runs', fakeAsync(() => {
    const router = TestBed.inject(Router);
    const location = TestBed.inject(Location);
    router.initialNavigation();
    tick();
    expect(location.path()).toEqual('/test_runs');
  }));

  it('should broadcast navigation target when onNavClick is called', () => {
    const navService = TestBed.inject(NavigationEventService);
    const notifySpy = spyOn(navService, 'notifyNavMenuClicked');
    mtt.onNavClick(NavigationTarget.DEVICES);
    expect(notifySpy).toHaveBeenCalledWith(NavigationTarget.DEVICES);
  });

  it('should return the common query params as preserved query params', () => {
    commonParams = {'debug': 'true'};
    expect(mtt.getPreservedQueryParams()).toEqual({'debug': 'true'});
  });

  it('should preserve the common query params on the Devices and Hosts links', () => {
    commonParams = {'debug': 'true', 'fake_data': '1'};
    mttFixture.detectChanges();
    expect(getEl(el, 'a[href*="/devices"]').getAttribute('href'))
        .toMatch(/\/devices\?debug=true&fake_data=1$/);
    expect(getEl(el, 'a[href*="/hosts"]').getAttribute('href'))
        .toMatch(/\/hosts\?debug=true&fake_data=1$/);
    // Other left nav links are not related to the V6 iframe.
    expect(getEl(el, 'a[href*="/test_runs"]').getAttribute('href'))
        .toMatch(/\/test_runs$/);
  });

  it('should keep the left nav links clean without common query params', () => {
    expect(getEl(el, 'a[href*="/devices"]').getAttribute('href'))
        .toMatch(/\/devices$/);
    expect(getEl(el, 'a[href*="/hosts"]').getAttribute('href'))
        .toMatch(/\/hosts$/);
  });

  it('should register the header slot for the routed pages', () => {
    const headerSlotService = TestBed.inject(HeaderSlotService);
    expect(headerSlotService.isAvailable()).toBeTrue();
    expect(headerSlotService.slotElement$.value)
        .toBe(getEl(el, '.header-slot'));
  });

  it('should render the version info in the footer, not in the header', () => {
    const footer = getEl(el, 'footer');
    expect(footer).toBeTruthy();
    expect(footer.querySelector('.version-info')!.textContent)
        .toContain('Version:');
    expect(footer.querySelectorAll('.version-info .separator').length).toBe(2);
    expect(getEl(el, 'mat-toolbar').querySelector('.version-info')).toBeNull();
    // No analytics tracking id => no privacy notice.
    expect(footer.querySelector('.privacy-notice')).toBeNull();
  });

  describe('Legacy UI switcher', () => {
    let urlSpy: jasmine.Spy|undefined;

    beforeEach(() => {
      urlSpy = undefined;
    });

    function setUrl(url: string) {
      urlSpy = urlSpy ?? spyOnProperty(TestBed.inject(Router), 'url', 'get');
      urlSpy.and.returnValue(url);
    }

    it('is shown on the Devices / Hosts search pages when the Lab Console search page is enabled',
       () => {
         appData.enableLabConsoleSearchPage = true;
         appData.enableLabConsoleUI = false;
         setUrl('/devices?includeOfflineDevices=false');
         expect(mtt.isLabConsoleTogglePage()).toBeTrue();
         setUrl('/hosts');
         expect(mtt.isLabConsoleTogglePage()).toBeTrue();
         // Detail pages are governed by the Lab Console UI flag.
         setUrl('/devices/serial-1');
         expect(mtt.isLabConsoleTogglePage()).toBeFalse();
       });

    it('is shown on the Devices / Hosts detail pages when the Lab Console UI is enabled',
       () => {
         appData.enableLabConsoleSearchPage = false;
         appData.enableLabConsoleUI = true;
         setUrl('/devices/serial-1?debug=true');
         expect(mtt.isLabConsoleTogglePage()).toBeTrue();
         setUrl('/hosts/host-1');
         expect(mtt.isLabConsoleTogglePage()).toBeTrue();
         setUrl('/devices');
         expect(mtt.isLabConsoleTogglePage()).toBeFalse();
       });

    it('is hidden on all other pages', () => {
      appData.enableLabConsoleSearchPage = true;
      appData.enableLabConsoleUI = true;
      for (const url of ['/test_plans', '/settings', '/test_runs/123', '/']) {
        setUrl(url);
        expect(mtt.isLabConsoleTogglePage()).withContext(url).toBeFalse();
      }
    });

    it('renders the switcher in the header and flips the Lab Console preference',
       () => {
         appData.enableLabConsoleSearchPage = true;
         setUrl('/devices');
         // Re-evaluated on every navigation.
         (TestBed.inject(Router).events as Subject<Event>)
             .next(new NavigationEnd(1, '/devices', '/devices'));
         mttFixture.detectChanges();

         const toggle =
             getEl(el, 'mat-toolbar .lab-console-ui-toggle button[role="switch"]');
         expect(toggle).toBeTruthy();
         expect(getEl(el, 'mat-toolbar .lab-console-ui-toggle').textContent)
             .toContain('Legacy UI');
         const before = mtt.preferenceService.useLabConsoleUISubject$.value;
         toggle.click();
         expect(mtt.preferenceService.useLabConsoleUISubject$.value)
             .toBe(!before);
       });
  });
});
