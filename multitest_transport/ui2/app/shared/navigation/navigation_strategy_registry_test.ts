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

import {TrustedResourceUrl, trustedResourceUrl} from 'safevalues';

import {NavigationStrategyRegistry} from './navigation_strategy_registry';
import {
  EntityType,
  MessagePage,
  PageNavigationStrategy,
  PageSpecificParamDefinition,
} from './page_navigation_strategy';

/** Test-only strategy declaring all kinds of page-specific params. */
class FakeNavigationStrategy extends PageNavigationStrategy {
  readonly pageType = 'device_search' as const;
  readonly entityType = EntityType.DEVICES;
  readonly isDetailPage = false;
  readonly pageSpecificParams: Readonly<
    Record<string, PageSpecificParamDefinition>
  > = {
    'same_key': true,
    'aliased': 'alias_source',
    'computed': (input) =>
      input['source'] ? `computed-${String(input['source'])}` : undefined,
  };

  isEnabled(): boolean {
    return true;
  }

  buildRoutePath(): string {
    return '/fake';
  }

  buildIframeBaseUrl(): TrustedResourceUrl {
    return trustedResourceUrl`/labui/fake`;
  }
}

/** Query params of a MTT search page URL, both allowed and unallowed. */
const SEARCH_ROUTE_PARAMS = {
  'f': 'filter1',
  'gb': 'group1',
  'fleet': 'ats',
  'q': 'pixel',
  'universe': 'ots',
  'debug': 'true',
  'lab': 'atl',
  'other': 'val',
};

describe('NavigationStrategyRegistry', () => {
  describe('lookups', () => {
    it('should return the search page strategies for entities without ID', () => {
      const devices = NavigationStrategyRegistry.forEntity(EntityType.DEVICES);
      const hosts = NavigationStrategyRegistry.forEntity(EntityType.HOSTS);
      expect(devices.pageType).toBe('device_search');
      expect(hosts.pageType).toBe('host_search');
    });

    it('should return the detail page strategies for entities with ID', () => {
      const device = NavigationStrategyRegistry.forEntity(
        EntityType.DEVICES,
        'device1',
      );
      const host = NavigationStrategyRegistry.forEntity(
        EntityType.HOSTS,
        'host1',
      );
      expect(device.pageType).toBe('device_detail');
      expect(host.pageType).toBe('host_detail');
    });

    it('should return the detail page strategies for external message pages', () => {
      const device = NavigationStrategyRegistry.forExternalMessagePage(
        MessagePage.DEVICE_DETAILS,
      );
      const host = NavigationStrategyRegistry.forExternalMessagePage(
        MessagePage.HOST_DETAILS,
      );
      expect(device.pageType).toBe('device_detail');
      expect(host.pageType).toBe('host_detail');
    });

    it('should return the strategies registered for page types', () => {
      const hostSearch = NavigationStrategyRegistry.getRequired('host_search');
      const deviceDetail =
        NavigationStrategyRegistry.getRequired('device_detail');
      expect(hostSearch.entityType).toBe(EntityType.HOSTS);
      expect(hostSearch.isDetailPage).toBeFalse();
      expect(deviceDetail.entityType).toBe(EntityType.DEVICES);
      expect(deviceDetail.isDetailPage).toBeTrue();
    });

    it('should throw for unsupported entity types and message pages', () => {
      expect(() =>
        NavigationStrategyRegistry.forEntity('jobs' as unknown as EntityType),
      ).toThrowError(/Unsupported entity type: jobs/);
      expect(() =>
        NavigationStrategyRegistry.forExternalMessagePage('job_details'),
      ).toThrowError(/Unsupported page type in external message: job/);
    });
  });

  describe('search page strategies', () => {
    it('should build the route path and the iframe base URL', () => {
      const devices = NavigationStrategyRegistry.getRequired('device_search');
      const hosts = NavigationStrategyRegistry.getRequired('host_search');
      expect(devices.buildRoutePath()).toBe('/devices');
      expect(devices.buildIframeBaseUrl().toString()).toBe('/labui/devices');
      expect(hosts.buildRoutePath()).toBe('/hosts');
      expect(hosts.buildIframeBaseUrl().toString()).toBe('/labui/hosts');
    });

    it('should be enabled by enableLabConsoleSearchPage only', () => {
      const strategy = NavigationStrategyRegistry.getRequired('device_search');
      expect(
        strategy.isEnabled({enableLabConsoleSearchPage: true}),
      ).toBeTrue();
      expect(strategy.isEnabled({enableLabConsoleUI: true})).toBeFalse();
      expect(strategy.isEnabled(null)).toBeFalse();
    });

    it('should forward only the search params (f, gb) and the common params', () => {
      const strategy = NavigationStrategyRegistry.getRequired('host_search');
      const url = strategy.buildIframeNavigateUrl(
        undefined,
        SEARCH_ROUTE_PARAMS,
        {},
      );
      expect(url).toBe(
        '/hosts?f=filter1&gb=group1&debug=true&is_embedded_mode=true',
      );
    });

    it('should drop the search params when resetting the search page', () => {
      const strategy = NavigationStrategyRegistry.getRequired('device_search');
      const url = strategy.buildIframeNavigateUrl(
        undefined,
        SEARCH_ROUTE_PARAMS,
        {},
        {resetPageSpecificParams: true},
      );
      expect(url).toBe('/devices?debug=true&is_embedded_mode=true');
    });

    it('should not support external messages', () => {
      const strategy = NavigationStrategyRegistry.getRequired('device_search');
      expect(strategy.externalMessagePage).toBeUndefined();
      expect(() =>
        strategy.extractEntityId({'device_uuid': 'device1'}),
      ).toThrowError(/does not support external messages/);
    });
  });

  describe('device detail page strategy', () => {
    let strategy: PageNavigationStrategy;

    beforeEach(() => {
      strategy = NavigationStrategyRegistry.getRequired('device_detail');
    });

    it('should build the route path and the iframe base URL', () => {
      expect(strategy.buildRoutePath('device1')).toBe('/devices/device1');
      expect(strategy.buildIframeBaseUrl('device1').toString()).toBe(
        '/labui/devices/device1',
      );
    });

    it('should require an entity ID', () => {
      expect(() => strategy.buildRoutePath()).toThrowError(
        /requires an entity ID/,
      );
    });

    it('should be enabled by enableLabConsoleUI only', () => {
      expect(strategy.isEnabled({enableLabConsoleUI: true})).toBeTrue();
      expect(
        strategy.isEnabled({enableLabConsoleSearchPage: true}),
      ).toBeFalse();
    });

    it('should not forward the search params', () => {
      const url = strategy.buildIframeNavigateUrl(
        'device1',
        SEARCH_ROUTE_PARAMS,
        {},
      );
      expect(url).toBe('/devices/device1?debug=true&is_embedded_mode=true');
    });

    it('should extract the device ID from device_uuid or uuid', () => {
      expect(strategy.externalMessagePage).toBe(MessagePage.DEVICE_DETAILS);
      expect(
        strategy.extractEntityId({'device_uuid': 'device1', 'uuid': 'other'}),
      ).toBe('device1');
      expect(strategy.extractEntityId({'uuid': 'device2'})).toBe('device2');
    });
  });

  describe('host detail page strategy', () => {
    let strategy: PageNavigationStrategy;

    beforeEach(() => {
      strategy = NavigationStrategyRegistry.getRequired('host_detail');
    });

    it('should build the route path and the iframe base URL', () => {
      expect(strategy.buildRoutePath('host1')).toBe('/hosts/host1');
      expect(strategy.buildIframeBaseUrl('host1').toString()).toBe(
        '/labui/hosts/host1',
      );
    });

    it('should be enabled by enableLabConsoleUI only', () => {
      expect(strategy.isEnabled({enableLabConsoleUI: true})).toBeTrue();
      expect(
        strategy.isEnabled({enableLabConsoleSearchPage: true}),
      ).toBeFalse();
    });

    it('should not forward the search params', () => {
      const url = strategy.buildIframeNavigateUrl(
        'host1',
        SEARCH_ROUTE_PARAMS,
        {},
      );
      expect(url).toBe('/hosts/host1?debug=true&is_embedded_mode=true');
    });

    it('should extract the hostname from host_name', () => {
      expect(strategy.externalMessagePage).toBe(MessagePage.HOST_DETAILS);
      expect(strategy.extractEntityId({'host_name': 'host1'})).toBe('host1');
    });
  });
});

describe('PageNavigationStrategy', () => {
  let strategy: FakeNavigationStrategy;

  beforeEach(() => {
    strategy = new FakeNavigationStrategy();
  });

  it('should extract the page-specific params following their definitions', () => {
    const params = strategy.extractPageSpecificParams({
      'same_key': 'v1',
      'alias_source': 'v2',
      'source': 'v3',
      'aliased': 'ignored',
      'other': 'ignored',
    });
    expect(Array.from(params.entries())).toEqual([
      ['same_key', ['v1']],
      ['aliased', ['v2']],
      ['computed', ['computed-v3']],
    ]);
  });

  it('should keep the repeated params as multiple values', () => {
    const url = strategy.buildIframeNavigateUrl(
      undefined,
      {'same_key': ['a', 'b']},
      {},
    );
    expect(url).toBe('/fake?same_key=a&same_key=b&is_embedded_mode=true');
  });

  it('should append the common params captured at SPA bootstrap', () => {
    const url = strategy.buildIframeNavigateUrl(
      undefined,
      {},
      {'debug': 'true', 'fake_data': '1'},
    );
    expect(url).toBe('/fake?debug=true&fake_data=1&is_embedded_mode=true');
  });

  it('should let the common params of the MTT URL override the captured ones', () => {
    const url = strategy.buildIframeNavigateUrl(
      undefined,
      {'debug': '1'},
      {'debug': 'true'},
    );
    expect(url).toBe('/fake?debug=1&is_embedded_mode=true');
  });

  it('should always force is_embedded_mode=true', () => {
    const url = strategy.buildIframeNavigateUrl(
      undefined,
      {'is_embedded_mode': 'false'},
      {},
    );
    expect(url).toBe('/fake?is_embedded_mode=true');
  });

  it('should build the initial iframe URL with the resolved params', () => {
    const url = strategy.buildInitialIframeUrl(
      undefined,
      {'same_key': 'v1', 'other': 'v2'},
      {'debug': 'true'},
    );
    expect(url.toString()).toBe(
      '/labui/fake?same_key=v1&debug=true&is_embedded_mode=true',
    );
  });

  it('should build the parent URL with the common params only', () => {
    expect(strategy.buildParentUrl(undefined, {})).toBe('/fake');
    expect(
      strategy.buildParentUrl(undefined, {'debug': 'true', 'fake_data': '1'}),
    ).toBe('/fake?debug=true&fake_data=1');
  });
});
