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

import {appendParams, TrustedResourceUrl} from 'safevalues';

import {AppData} from '../../services/app_data';
import {isCommonQueryParam} from '../../services/common_params_service';

/**
 * Entity types supported by the V6 iframe container.
 */
export enum EntityType {
  HOSTS = 'hosts',
  DEVICES = 'devices',
}

/**
 * Message pages supported by the V6 iframe container.
 */
export enum MessagePage {
  HOST_DETAILS = 'host_details',
  DEVICE_DETAILS = 'device_details',
}

/**
 * Query parameter telling the LabConsole (MHFE V6) app that it is embedded in
 * MTT UI2. It is always set to 'true' on the iframe URLs.
 */
export const EMBEDDED_MODE_PARAM = 'is_embedded_mode';

/** Page types of the LabConsole (MHFE V6) pages embedded in MTT UI2. */
export type V6PageType =
  | 'device_search'
  | 'host_search'
  | 'device_detail'
  | 'host_detail';

/**
 * Input query parameters, e.g. the Angular route query params of the current
 * MTT URL, or the `params` of a message posted by the LabConsole iframe.
 */
export type QueryParamsInput = Readonly<Record<string, unknown>>;

/**
 * Resolved query parameters, ordered by insertion. A key maps to multiple
 * values for a repeated query parameter (e.g. `?f=a&f=b`).
 */
export type ResolvedQueryParams = Map<string, string[]>;

/**
 * Extracts the value(s) of a page-specific query parameter from the input
 * query parameters, or returns undefined to omit the query parameter.
 */
export type ParamExtractorFn = (
  input: QueryParamsInput,
) => string | readonly string[] | undefined;

/**
 * Declarative definition of a page-specific query parameter:
 * - `true`: copies the input query parameter with the same key.
 * - `string`: copies the input query parameter with this alias key.
 * - `ParamExtractorFn`: computes the value(s) from the input query parameters.
 */
export type PageSpecificParamDefinition = true | string | ParamExtractorFn;

/** Options for resolving the query parameters of an iframe URL. */
export interface IframeQueryParamsOptions {
  /**
   * Whether to drop the page-specific query parameters (e.g. f, gb), e.g. when
   * resetting a search page from the left navigation menu.
   */
  readonly resetPageSpecificParams?: boolean;
}

/**
 * Normalizes a query parameter value into a list of strings.
 *
 * @param value The query parameter value: a single value, or an array of
 *     values for a repeated query parameter.
 * @return The list of string values, without the null or undefined values.
 */
export function toQueryParamValues(value: unknown): string[] {
  const values: unknown[] = Array.isArray(value) ? value : [value];
  return values.filter((v) => v !== null && v !== undefined).map(String);
}

/**
 * Abstract navigation strategy of a LabConsole (MHFE V6) page embedded in MTT
 * UI2, applying the Strategy and Template Method patterns.
 *
 * Each concrete strategy only declares what is specific to its page: its route
 * path, its iframe base URL, its positive whitelist of page-specific query
 * parameters, and the AppData flag enabling it. This base class implements the
 * invariant algorithms composing the iframe URLs and the parent (MTT) URLs out
 * of these declarations, so that supporting a new page only requires
 * registering a new strategy in the NavigationStrategyRegistry, without
 * modifying any caller (Open/Closed Principle).
 */
export abstract class PageNavigationStrategy {
  /** Unique page type of the page, used as the registry key. */
  abstract readonly pageType: V6PageType;

  /** Entity type of the page. */
  abstract readonly entityType: EntityType;

  /** Whether the page is an entity detail page (otherwise a search page). */
  abstract readonly isDetailPage: boolean;

  /**
   * Page-specific query parameters forwarded from the MTT URL to the iframe
   * URL, keyed by the iframe query parameter name. It is a positive whitelist:
   * the query parameters of the MTT URL that are neither declared here nor
   * common query parameters are never forwarded to the iframe.
   */
  abstract readonly pageSpecificParams: Readonly<
    Record<string, PageSpecificParamDefinition>
  >;

  /**
   * Page name used by the messages (GET_EXTERNAL_URL, NAVIGATED) posted by the
   * LabConsole iframe for this page, or undefined if not supported.
   */
  readonly externalMessagePage?: MessagePage;

  /**
   * Checks whether the embedded LabConsole page is enabled.
   *
   * @param appData The MTT application data.
   * @return True if the AppData flag of the page is set, false otherwise.
   */
  abstract isEnabled(appData: AppData | null | undefined): boolean;

  /**
   * Builds the route path of the page (e.g. `/devices/<id>`). MTT UI2 mirrors
   * the LabConsole routes, so the same path is used both in the parent (MTT)
   * URL and for the in-iframe navigation.
   *
   * @param id The entity ID, required by the detail pages.
   * @return The route path.
   */
  abstract buildRoutePath(id?: string): string;

  /**
   * Builds the base URL of the iframe (e.g. `/labui/devices/<id>`).
   *
   * @param id The entity ID, required by the detail pages.
   * @return The iframe base URL, without query parameters.
   */
  abstract buildIframeBaseUrl(id?: string): TrustedResourceUrl;

  /**
   * Extracts the entity ID from the `params` of a GET_EXTERNAL_URL or
   * NAVIGATED message posted by the LabConsole iframe. Only supported by the
   * pages declaring an externalMessagePage.
   *
   * @param messageParams The `params` of the message.
   * @return The entity ID, or undefined if the message does not carry one (the
   *     URL builders then reject it through requireId).
   */
  extractEntityId(messageParams: QueryParamsInput): string | undefined {
    throw new Error(
      `Page type ${this.pageType} does not support external messages, ` +
        `params: ${JSON.stringify(messageParams)}`,
    );
  }

  /**
   * Extracts the page-specific query parameters from the input query
   * parameters, following the definitions declared in pageSpecificParams.
   *
   * @param input The input query parameters.
   * @return The page-specific query parameters, in declaration order.
   */
  extractPageSpecificParams(input: QueryParamsInput): ResolvedQueryParams {
    const result: ResolvedQueryParams = new Map();
    for (const [key, definition] of Object.entries(this.pageSpecificParams)) {
      const values = toQueryParamValues(
        this.extractParamValue(key, definition, input),
      );
      if (values.length > 0) {
        result.set(key, values);
      }
    }
    return result;
  }

  /**
   * Resolves the query parameters of an iframe URL of this page.
   *
   * @param routeParams The query parameters of the current MTT URL.
   * @param commonParams The common query parameters captured at SPA bootstrap.
   * @param options Options, e.g. to reset the page-specific query parameters.
   * @return The resolved query parameters of the iframe URL.
   *
   * Explanation:
   * Composes, in this order:
   *   1. The page-specific query parameters (e.g. f, gb on the search pages),
   *      unless resetPageSpecificParams is set.
   *   2. The common query parameters captured at SPA bootstrap (e.g. debug,
   *      fake_data), overridden by the ones explicitly present on the current
   *      MTT URL (e.g. `?debug=1`).
   *   3. is_embedded_mode=true, which is always set on the iframe URLs.
   * Any other query parameter of the MTT URL is not forwarded to the iframe.
   */
  resolveIframeQueryParams(
    routeParams: QueryParamsInput,
    commonParams: Readonly<Record<string, string>>,
    options: IframeQueryParamsOptions = {},
  ): ResolvedQueryParams {
    const result: ResolvedQueryParams = options.resetPageSpecificParams
      ? new Map()
      : this.extractPageSpecificParams(routeParams);
    for (const [key, value] of Object.entries(commonParams)) {
      result.set(key, [value]);
    }
    for (const [key, value] of Object.entries(routeParams)) {
      const values = toQueryParamValues(value);
      if (isCommonQueryParam(key) && values.length > 0) {
        result.set(key, values);
      }
    }
    result.set(EMBEDDED_MODE_PARAM, ['true']);
    return result;
  }

  /**
   * Builds the initial `src` URL of the iframe for this page.
   *
   * @param id The entity ID, required by the detail pages.
   * @param routeParams The query parameters of the current MTT URL.
   * @param commonParams The common query parameters captured at SPA bootstrap.
   * @return The iframe URL (e.g. `/labui/hosts?f=...&is_embedded_mode=true`).
   */
  buildInitialIframeUrl(
    id: string | undefined,
    routeParams: QueryParamsInput,
    commonParams: Readonly<Record<string, string>>,
  ): TrustedResourceUrl {
    return appendParams(
      this.buildIframeBaseUrl(id),
      this.resolveIframeQueryParams(routeParams, commonParams),
    );
  }

  /**
   * Builds the URL to navigate the already loaded iframe to this page (with a
   * NAVIGATE message), relative to the LabConsole app.
   *
   * @param id The entity ID, required by the detail pages.
   * @param routeParams The query parameters of the current MTT URL.
   * @param commonParams The common query parameters captured at SPA bootstrap.
   * @param options Options, e.g. to reset the page-specific query parameters.
   * @return The URL (e.g. `/hosts?f=...&is_embedded_mode=true`).
   */
  buildIframeNavigateUrl(
    id: string | undefined,
    routeParams: QueryParamsInput,
    commonParams: Readonly<Record<string, string>>,
    options: IframeQueryParamsOptions = {},
  ): string {
    const searchParams = new URLSearchParams();
    const queryParams = this.resolveIframeQueryParams(
      routeParams,
      commonParams,
      options,
    );
    for (const [key, values] of queryParams.entries()) {
      for (const value of values) {
        searchParams.append(key, value);
      }
    }
    return `${this.buildRoutePath(id)}?${searchParams.toString()}`;
  }

  /**
   * Builds the URL of this page in MTT UI2 (relative to the MTT origin), which
   * only carries the common query parameters.
   *
   * @param id The entity ID, required by the detail pages.
   * @param commonParams The common query parameters captured at SPA bootstrap.
   * @return The URL (e.g. `/hosts/<id>?debug=true`).
   */
  buildParentUrl(
    id: string | undefined,
    commonParams: Readonly<Record<string, string>>,
  ): string {
    const path = this.buildRoutePath(id);
    const search = new URLSearchParams(commonParams).toString();
    return search ? `${path}?${search}` : path;
  }

  /**
   * Returns the entity ID required by a detail page, or throws if missing.
   *
   * @param id The entity ID.
   * @return The entity ID.
   */
  protected requireId(id: string | undefined): string {
    if (!id) {
      throw new Error(`Page type ${this.pageType} requires an entity ID.`);
    }
    return id;
  }

  private extractParamValue(
    key: string,
    definition: PageSpecificParamDefinition,
    input: QueryParamsInput,
  ): unknown {
    if (definition === true) {
      return input[key];
    }
    if (typeof definition === 'string') {
      return input[definition];
    }
    return definition(input);
  }
}
