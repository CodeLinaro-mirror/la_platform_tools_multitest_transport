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
import {Router, RouterModule} from '@angular/router';
import {of as observableOf} from 'rxjs';

import {Mtt, MttModule} from './app';
import {AnalyticsService} from './services/analytics_service';
import {APP_DATA} from './services/app_data';
import {UserService} from './services/user_service';
import {getEl} from './testing/jasmine_util';

describe('Mtt', () => {
  let mtt: Mtt;
  let mttFixture: ComponentFixture<Mtt>;
  let el: DebugElement;
  let analyticsServiceSpy: jasmine.SpyObj<AnalyticsService>;
  let userServiceSpy: jasmine.SpyObj<UserService>;

  beforeEach(() => {
    analyticsServiceSpy = jasmine.createSpyObj(['trackLocation']);
    userServiceSpy = jasmine.createSpyObj('userService', {
      checkPermission: observableOf(true),
      setAdmin: undefined,
    });

    TestBed.configureTestingModule({
      imports: [MttModule, RouterModule],
      providers: [
        {provide: APP_DATA, useValue: {netdataUrl: 'localhost:8008'}},
        {provide: AnalyticsService, useValue: analyticsServiceSpy},
        {provide: UserService, useValue: userServiceSpy},
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
});
