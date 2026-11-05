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

import {trustedResourceUrl} from 'safevalues';

import {DeviceDetailNavigationStrategy} from './device_detail_navigation_strategy';
import {HostDetailNavigationStrategy} from './host_detail_navigation_strategy';
import {
  EntityType,
  PageNavigationStrategy,
  V6PageType,
} from './page_navigation_strategy';
import {SearchNavigationStrategy} from './search_navigation_strategy';

/**
 * Search query parameters of the LabConsole search pages, which are forwarded
 * from the MTT URL to the iframe.
 */
const SEARCH_PAGE_SPECIFIC_PARAMS = [
  'f', // the filter
  'gb', // the group by
  // 'fleet', // fleet is NOT supported in OSS
  // 'q', // the query text. This is useless as it's the tmp status.
  // 'universe', // universe is NOT supported in OSS
] as const;

/**
 * Registry holding the navigation strategies of the LabConsole (MHFE V6) pages
 * embedded in MTT UI2.
 * Provides lookups by page type, by entity, and by the page name of the
 * messages posted by the iframe, and allows extending with new page types.
 */
// tslint:disable-next-line:class-as-namespace
export class NavigationStrategyRegistry {
  private static readonly strategies = new Map<
    V6PageType,
    PageNavigationStrategy
  >();

  /**
   * Registers a navigation strategy, replacing the strategy previously
   * registered for the same page type, if any.
   *
   * @param strategy The navigation strategy.
   * @return void
   */
  static register(strategy: PageNavigationStrategy): void {
    NavigationStrategyRegistry.strategies.set(strategy.pageType, strategy);
  }

  /**
   * Returns the strategy registered for a page type.
   *
   * @param pageType The page type.
   * @return The navigation strategy, or throws if not registered.
   */
  static getRequired(pageType: V6PageType): PageNavigationStrategy {
    const strategy = NavigationStrategyRegistry.strategies.get(pageType);
    if (!strategy) {
      throw new Error(
        `No navigation strategy registered for page type: ${pageType}`,
      );
    }
    return strategy;
  }

  /**
   * Returns the strategy of the search page or of the detail page of an
   * entity type.
   *
   * @param type The entity type (hosts or devices).
   * @param id The optional entity ID (if provided, returns the detail page).
   * @return The navigation strategy, or throws if not supported.
   */
  static forEntity(type: EntityType, id?: string): PageNavigationStrategy {
    const isDetailPage = !!id;
    return NavigationStrategyRegistry.find(
      (strategy) =>
        strategy.entityType === type && strategy.isDetailPage === isDetailPage,
      `Unsupported entity type: ${type}`,
    );
  }

  /**
   * Returns the strategy of the page named by a GET_EXTERNAL_URL or NAVIGATED
   * message posted by the LabConsole iframe.
   *
   * @param page The page name of the message (e.g. 'host_details').
   * @return The navigation strategy, or throws if not supported.
   */
  static forExternalMessagePage(page: string): PageNavigationStrategy {
    return NavigationStrategyRegistry.find(
      (strategy) =>
        strategy.externalMessagePage !== undefined &&
        strategy.externalMessagePage === page,
      `Unsupported page type in external message: ${page}`,
    );
  }

  private static find(
    predicate: (strategy: PageNavigationStrategy) => boolean,
    errorMessage: string,
  ): PageNavigationStrategy {
    for (const strategy of NavigationStrategyRegistry.strategies.values()) {
      if (predicate(strategy)) {
        return strategy;
      }
    }
    throw new Error(errorMessage);
  }
}

// Register the search page strategies in the registry.
NavigationStrategyRegistry.register(
  new SearchNavigationStrategy({
    pageType: 'device_search',
    entityType: EntityType.DEVICES,
    routePath: '/devices',
    iframeBaseUrl: trustedResourceUrl`/labui/devices`,
    searchParams: SEARCH_PAGE_SPECIFIC_PARAMS,
  }),
);
NavigationStrategyRegistry.register(
  new SearchNavigationStrategy({
    pageType: 'host_search',
    entityType: EntityType.HOSTS,
    routePath: '/hosts',
    iframeBaseUrl: trustedResourceUrl`/labui/hosts`,
    searchParams: SEARCH_PAGE_SPECIFIC_PARAMS,
  }),
);

// Register the detail page strategies in the registry.
NavigationStrategyRegistry.register(new DeviceDetailNavigationStrategy());
NavigationStrategyRegistry.register(new HostDetailNavigationStrategy());
