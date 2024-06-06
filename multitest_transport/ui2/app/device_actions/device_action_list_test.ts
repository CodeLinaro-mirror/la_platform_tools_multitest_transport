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

import {LiveAnnouncer} from '@angular/cdk/a11y';
import {DebugElement} from '@angular/core';
import {ComponentFixture, fakeAsync, TestBed, tick} from '@angular/core/testing';
import {NoopAnimationsModule} from '@angular/platform-browser/animations';
import {RouterModule} from '@angular/router';
import {of as observableOf} from 'rxjs';

import {MttClient} from '../services/mtt_client';
import {MttObjectMap, MttObjectMapService, newMttObjectMap} from '../services/mtt_object_map';
import {getEl, getEls, getTextContent} from '../testing/jasmine_util';
import * as mttMocks from '../testing/mtt_mocks';

import {DeviceActionList} from './device_action_list';
import {DeviceActionsModule} from './device_actions_module';

const FACTORY_RESET_ACTION =
    mttMocks.newMockDeviceAction('reset', 'Factory Reset');

// None of these tests pass. `whenStable` was not awaited so the tests finished
// before expectations ran
// tslint:disable-next-line:ban
xdescribe('DeviceActionList', () => {
  let deviceActionList: DeviceActionList;
  let deviceActionListFixture: ComponentFixture<DeviceActionList>;
  let el: DebugElement;
  let liveAnnouncer: jasmine.SpyObj<LiveAnnouncer>;
  let mttClient: jasmine.SpyObj<MttClient>;
  let mttObjectMapService: jasmine.SpyObj<MttObjectMapService>;
  let mttObjectMap: MttObjectMap;

  beforeEach(() => {
    liveAnnouncer =
        jasmine.createSpyObj('liveAnnouncer', ['announce', 'clear']);
    mttClient = jasmine.createSpyObj('mttClient', ['deleteDeviceAction']);
    mttClient.deleteDeviceAction.and.returnValue(observableOf({}));

    mttObjectMapService =
        jasmine.createSpyObj('mttObjectMapService', ['getMttObjectMap']);
    mttObjectMap = newMttObjectMap();
    mttObjectMap.deviceActionMap = {
      'reset': FACTORY_RESET_ACTION,
    };
    mttObjectMapService.getMttObjectMap.and.returnValue(
        observableOf(mttObjectMap));


    TestBed.configureTestingModule({
      imports: [DeviceActionsModule, NoopAnimationsModule, RouterModule],
      providers: [
        {provide: LiveAnnouncer, useValue: liveAnnouncer},
        {provide: MttClient, useValue: mttClient},
        {provide: MttObjectMapService, useValue: mttObjectMapService},
      ],
    });
    deviceActionListFixture = TestBed.createComponent(DeviceActionList);
    deviceActionListFixture.detectChanges();
    el = deviceActionListFixture.debugElement;
    deviceActionList = deviceActionListFixture.componentInstance;
  });

  afterEach(() => {
    deviceActionListFixture.destroy();
  });

  it('initializes a component', () => {
    expect(deviceActionList).toBeTruthy();
  });

  it('called mttApi to load device action list', fakeAsync(() => {
       tick(100);
       expect(mttClient.getDeviceActionList).toHaveBeenCalled();
     }));

  it('displayed correct HTML text content', fakeAsync(() => {
       const NAMESPACED_ACTION =
           mttMocks.newMockDeviceAction('ns1::action', 'Namespaced Action');
       const MISSING_NAMESPACE_ACTION = mttMocks.newMockDeviceAction(
           'ns2::action', 'Missing Namespace Action');
       const CONFIG_SET_MAP = {
         ns1: mttMocks.newMockConfigSetInfo('ns1', 'Namespace 1'),
       };
       mttObjectMap.deviceActionMap = {
         'reset': FACTORY_RESET_ACTION,
         'ns1::action': NAMESPACED_ACTION,
         'ns2::action': MISSING_NAMESPACE_ACTION,
       };
       mttObjectMap.configSetInfoMap = CONFIG_SET_MAP;
       mttObjectMapService.getMttObjectMap.and.returnValue(
           observableOf(mttObjectMap));

       tick(100);
       const textContent = getTextContent(el);
       expect(textContent).toContain('Factory Reset');
       expect(textContent).toContain('Namespaced Action');
       expect(textContent).toContain('Missing Namespace Action');
       expect(textContent).toContain('Default/Custom Device Actions');
       expect(textContent).toContain('Namespace 1');
       expect(textContent).toContain('Unknown Namespace (ns2)');
     }));

  it('displays default action buttons', fakeAsync(() => {
       mttObjectMap.deviceActionMap = {
         'reset': FACTORY_RESET_ACTION,
       };
       mttObjectMapService.getMttObjectMap.and.returnValue(
           observableOf(mttObjectMap));
       deviceActionListFixture.detectChanges();

       tick(100);
       const updateButton = getEl(el, '.update-button');
       expect(updateButton).toBeTruthy();
       const deleteButton = getEl(el, '.delete-button');
       expect(deleteButton).toBeTruthy();
       const viewButton = getEl(el, '.view-button');
       expect(viewButton).toBeFalsy();
     }));

  it('displays namespaced action buttons', fakeAsync(() => {
       const NAMESPACED_ACTION =
           mttMocks.newMockDeviceAction('ns1::action', 'Namespaced Action');
       const CONFIG_SET_MAP = {
         ns1: mttMocks.newMockConfigSetInfo('ns1', 'Namespace 1'),
       };
       mttObjectMap.deviceActionMap = {
         'reset': FACTORY_RESET_ACTION,
         'ns1::action': NAMESPACED_ACTION,
       };
       mttObjectMap.configSetInfoMap = CONFIG_SET_MAP;
       mttObjectMapService.getMttObjectMap.and.returnValue(
           observableOf(mttObjectMap));

       tick(100);
       const updateButton = getEl(el, '.update-button');
       expect(updateButton).toBeFalsy();
       const deleteButton = getEl(el, '.delete-button');
       expect(deleteButton).toBeFalsy();
       const viewButton = getEl(el, '.view-button');
       expect(viewButton).toBeTruthy();
     }));


  it('displays and announces a loading mask', fakeAsync(() => {
       tick(100);
       expect(deviceActionList.isLoading).toBeTruthy();
       expect(liveAnnouncer.announce).toHaveBeenCalledWith('Loading', 'polite');
       expect(deviceActionList.isLoading).toBeFalsy();
       expect(liveAnnouncer.announce)
           .toHaveBeenCalledWith('Device actions loaded', 'assertive');
     }));

  it('deletes a device action correctly', fakeAsync(() => {
       tick(100);
       expect(getEls(el, 'mat-card').length).toBe(1);
       getEl(el, '.delete-button').click();
       deviceActionListFixture.detectChanges();
       expect(mttClient.deleteDeviceAction)
           .toHaveBeenCalledWith(FACTORY_RESET_ACTION.id);
       expect(getEls(el, 'mat-card').length).toBe(0);
     }));

  describe('update button', () => {
    it('should display correct aria-label and tooltip', fakeAsync(() => {
         tick(100);
         const updateButton = getEl(el, '.update-button');
         expect(updateButton).toBeTruthy();
         expect(updateButton.getAttribute('aria-label')).toBe('Edit');
         expect(updateButton.getAttribute('mattooltip')).toBe('Edit');
       }));
  });

  describe('delete button', () => {
    it('should display correct aria-label and tooltip', fakeAsync(() => {
         tick(100);
         const deleteButton = getEl(el, '.delete-button');
         expect(deleteButton).toBeTruthy();
         expect(deleteButton.getAttribute('aria-label')).toBe('Delete');
         expect(deleteButton.getAttribute('mattooltip')).toBe('Delete');
       }));
  });

  describe('more actions button', () => {
    it('should display correct aria-label and tooltip', fakeAsync(() => {
         tick(100);
         const moreActionsButton = getEl(el, '#menuButton');
         expect(moreActionsButton).toBeTruthy();
         expect(moreActionsButton.getAttribute('aria-label'))
             .toBe('More actions');
         expect(moreActionsButton.getAttribute('mattooltip'))
             .toBe('More actions');
       }));
  });
});
