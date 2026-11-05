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

import {TrustedResourceUrl} from 'safevalues';

import {AppData} from '../../services/app_data';

import {
  EntityType,
  PageNavigationStrategy,
  PageSpecificParamDefinition,
  V6PageType,
} from './page_navigation_strategy';

/** Configuration of a LabConsole search page. */
export interface SearchPageConfig {
  /** Unique page type of the search page (e.g. 'device_search'). */
  readonly pageType: V6PageType;
  /** Entity type searched by the page. */
  readonly entityType: EntityType;
  /** Route path of the search page (e.g. '/devices'). */
  readonly routePath: string;
  /** Base URL of the iframe (e.g. trustedResourceUrl`/labui/devices`). */
  readonly iframeBaseUrl: TrustedResourceUrl;
  /** Search query parameters forwarded to the iframe (e.g. ['f', 'gb']). */
  readonly searchParams: readonly string[];
}

/**
 * Navigation strategy of the LabConsole search pages (e.g. `/devices`,
 * `/hosts`), which are enabled by the enableLabConsoleSearchPage AppData flag.
 */
export class SearchNavigationStrategy extends PageNavigationStrategy {
  readonly pageType: V6PageType;
  readonly entityType: EntityType;
  readonly isDetailPage = false;
  readonly pageSpecificParams: Readonly<
    Record<string, PageSpecificParamDefinition>
  >;

  private readonly routePath: string;
  private readonly iframeBaseUrl: TrustedResourceUrl;

  constructor(config: SearchPageConfig) {
    super();
    this.pageType = config.pageType;
    this.entityType = config.entityType;
    this.routePath = config.routePath;
    this.iframeBaseUrl = config.iframeBaseUrl;
    const pageSpecificParams: Record<string, PageSpecificParamDefinition> = {};
    for (const param of config.searchParams) {
      pageSpecificParams[param] = true;
    }
    this.pageSpecificParams = pageSpecificParams;
  }

  isEnabled(appData: AppData | null | undefined): boolean {
    return Boolean(appData?.enableLabConsoleSearchPage);
  }

  buildRoutePath(): string {
    return this.routePath;
  }

  buildIframeBaseUrl(): TrustedResourceUrl {
    return this.iframeBaseUrl;
  }
}
