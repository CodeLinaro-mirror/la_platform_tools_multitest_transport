/**
 * Copyright 2026 Google LLC
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

import {TestBed} from '@angular/core/testing';

import {APP_DATA, AppData} from '../../services/app_data';
import {CommonParamsService} from '../../services/common_params_service';
import {NavigationTarget} from '../../services/navigation_event_service';

import {EntityType, MessagePage} from './page_navigation_strategy';
import {V6NavigationService} from './v6_navigation_service';

describe('V6NavigationService', () => {
  let commonParams: Record<string, string>;

  /** Creates the service with the given AppData flags. */
  function createService(
    appData: AppData = {
      enableLabConsoleUI: true,
      enableLabConsoleSearchPage: true,
    },
  ): V6NavigationService {
    TestBed.configureTestingModule({
      providers: [
        {provide: APP_DATA, useValue: appData},
        {
          provide: CommonParamsService,
          useValue: {getCommonParams: () => commonParams},
        },
      ],
    });
    return TestBed.inject(V6NavigationService);
  }

  beforeEach(() => {
    commonParams = {};
  });

  describe('isEntityPageEnabled', () => {
    it('should check enableLabConsoleSearchPage for the search pages', () => {
      const service = createService({enableLabConsoleSearchPage: true});
      expect(service.isEntityPageEnabled(EntityType.DEVICES)).toBeTrue();
      expect(service.isEntityPageEnabled(EntityType.HOSTS)).toBeTrue();
      expect(service.isEntityPageEnabled(EntityType.DEVICES, 'd1')).toBeFalse();
      expect(service.isEntityPageEnabled(EntityType.HOSTS, 'h1')).toBeFalse();
    });

    it('should check enableLabConsoleUI for the detail pages', () => {
      const service = createService({enableLabConsoleUI: true});
      expect(service.isEntityPageEnabled(EntityType.DEVICES)).toBeFalse();
      expect(service.isEntityPageEnabled(EntityType.HOSTS)).toBeFalse();
      expect(service.isEntityPageEnabled(EntityType.DEVICES, 'd1')).toBeTrue();
      expect(service.isEntityPageEnabled(EntityType.HOSTS, 'h1')).toBeTrue();
    });
  });

  describe('buildInitialIframeUrl', () => {
    it('should build the search page URL with the search and common params', () => {
      commonParams = {'fake_data': '1'};
      const url = createService().buildInitialIframeUrl(
        EntityType.DEVICES,
        undefined,
        {'f': 'f1', 'q': 'pixel', 'debug': 'true'},
      );
      expect(url.toString()).toBe(
        '/labui/devices?f=f1&fake_data=1&debug=true&is_embedded_mode=true',
      );
    });

    it('should build the detail page URL without the search params', () => {
      const url = createService().buildInitialIframeUrl(
        EntityType.HOSTS,
        'host1',
        {'f': 'filter1', 'gb': 'group1', 'debug': 'true'},
      );
      expect(url.toString()).toBe(
        '/labui/hosts/host1?debug=true&is_embedded_mode=true',
      );
    });
  });

  describe('buildEntityIframeNavigateUrl', () => {
    it('should retain the search params (f, gb) on the search pages', () => {
      const url = createService().buildEntityIframeNavigateUrl(
        EntityType.HOSTS,
        undefined,
        {
          'f': 'filter1',
          'gb': 'group1',
          'fleet': 'ats',
          'q': 'pixel',
          'debug': 'true',
          'other': 'val',
        },
      );
      expect(url).toBe(
        '/hosts?f=filter1&gb=group1&debug=true&is_embedded_mode=true',
      );
    });

    it('should append the captured common params on the detail pages', () => {
      commonParams = {'debug': 'true', 'fake_data': '1'};
      const url = createService().buildEntityIframeNavigateUrl(
        EntityType.HOSTS,
        'host1',
        {},
      );
      expect(url).toBe(
        '/hosts/host1?debug=true&fake_data=1&is_embedded_mode=true',
      );
    });

    it('should not overwrite the common params of the current MTT URL', () => {
      commonParams = {'debug': 'true'};
      const url = createService().buildEntityIframeNavigateUrl(
        EntityType.DEVICES,
        'device1',
        {'debug': '1'},
      );
      expect(url).toBe('/devices/device1?debug=1&is_embedded_mode=true');
    });
  });

  describe('buildSearchResetIframeUrl', () => {
    it('should drop the search params but keep the common params', () => {
      commonParams = {'fake_data': '1'};
      const url = createService().buildSearchResetIframeUrl(
        NavigationTarget.DEVICES,
        {'f': 'filter1', 'q': 'pixel', 'debug': 'true', 'lab': 'atl'},
      );
      expect(url).toBe(
        '/devices?fake_data=1&debug=true&is_embedded_mode=true',
      );
    });

    it('should reset the search page of the clicked target', () => {
      const url = createService().buildSearchResetIframeUrl(
        NavigationTarget.HOSTS,
        {'f': 'filter1', 'gb': 'group1'},
      );
      expect(url).toBe('/hosts?is_embedded_mode=true');
    });
  });

  describe('external messages', () => {
    it('should resolve the absolute external URL with the common params', () => {
      commonParams = {'debug': 'true', 'fake_data': '1'};
      const url = createService().resolveExternalUrl(
        MessagePage.HOST_DETAILS,
        {'host_name': 'host4'},
        'https://mtt.example.com',
      );
      expect(url).toBe(
        'https://mtt.example.com/hosts/host4?debug=true&fake_data=1',
      );
    });

    it('should resolve the parent URL of the NAVIGATED pages', () => {
      const service = createService();
      expect(
        service.resolveNavigatedParentUrl(MessagePage.HOST_DETAILS, {
          'host_name': 'host3',
        }),
      ).toBe('/hosts/host3');
      expect(
        service.resolveNavigatedParentUrl(MessagePage.DEVICE_DETAILS, {
          'device_uuid': 'device1',
        }),
      ).toBe('/devices/device1');
      expect(
        service.resolveNavigatedParentUrl(MessagePage.DEVICE_DETAILS, {
          'uuid': 'device2',
        }),
      ).toBe('/devices/device2');
    });

    it('should throw for unsupported message pages', () => {
      const service = createService();
      expect(() =>
        service.resolveNavigatedParentUrl('job_details', {'job_id': 'job1'}),
      ).toThrowError(/Unsupported page type in external message/);
    });

    it('should reject detail page messages without an entity ID', () => {
      const service = createService();
      expect(() =>
        service.resolveNavigatedParentUrl(MessagePage.DEVICE_DETAILS, {}),
      ).toThrowError(/requires an entity ID/);
      expect(() =>
        service.resolveNavigatedParentUrl(MessagePage.HOST_DETAILS, {}),
      ).toThrowError(/requires an entity ID/);
    });

    it('should merge the common params into the search state params', () => {
      commonParams = {'debug': 'true', 'fake_data': '1'};
      expect(
        createService().resolveSearchStateParentQueryParams({'q': 'pixel'}),
      ).toEqual({'debug': 'true', 'fake_data': '1', 'q': 'pixel'});
    });
  });
});
