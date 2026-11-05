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

import {DOCUMENT} from '@angular/common';
import {inject, Injectable} from '@angular/core';

/**
 * Common query parameters of MTT UI2, which persist in memory across the
 * client-side SPA navigations and are forwarded to the embedded LabConsole
 * (MHFE V6) iframe.
 */
export const COMMON_QUERY_PARAMS = ['debug', 'fake_data'] as const;

/** Key type of the supported common query parameters. */
export type CommonQueryParamKey = (typeof COMMON_QUERY_PARAMS)[number];

const COMMON_QUERY_PARAM_SET: ReadonlySet<string> = new Set<string>(
  COMMON_QUERY_PARAMS,
);

/**
 * Values activating a common query parameter. Other values (e.g. 'false') are
 * ignored when capturing the common query parameters.
 */
const ACTIVE_COMMON_QUERY_PARAM_VALUES: ReadonlySet<string> = new Set([
  'true',
  '1',
]);

/**
 * Checks whether a query parameter is a common query parameter.
 *
 * @param key The query parameter key.
 * @return True if the key is one of COMMON_QUERY_PARAMS, false otherwise.
 */
export function isCommonQueryParam(key: string): key is CommonQueryParamKey {
  return COMMON_QUERY_PARAM_SET.has(key);
}

/**
 * Parses the active common query parameters from a URL search string.
 *
 * @param search The URL search string (e.g. '?debug=true&fake_data=1').
 * @return Frozen record of the active common query parameters.
 *
 * Explanation:
 * Only the common query parameters (e.g. debug, fake_data) whose value is
 * 'true' or '1' are captured, so that e.g. '?debug=false' does not activate
 * the debug mode.
 */
export function parseCommonQueryParams(
  search: string,
): Readonly<Record<string, string>> {
  const result: Record<string, string> = {};
  for (const [key, value] of new URLSearchParams(search).entries()) {
    if (
      isCommonQueryParam(key) &&
      ACTIVE_COMMON_QUERY_PARAM_VALUES.has(value)
    ) {
      result[key] = value;
    }
  }
  return Object.freeze(result);
}

/**
 * Service capturing the Common Query Parameters of MTT UI2 (e.g. debug,
 * fake_data).
 *
 * The common query parameters are captured once from the initial page URL
 * when this service is instantiated, which happens when the root `Mtt`
 * component is created at SPA bootstrap (i.e. before the initial navigation).
 * They are then preserved in memory across the client-side SPA navigations for
 * the tab's lifetime, naturally reset on a full page reload (Ctrl+R), and do
 * not leak across tabs.
 *
 * Being an injectable service instead of a module-level mutable variable, each
 * TestBed gets its own isolated instance, so unit tests can provide a fake
 * DOCUMENT (or a fake service) without mutating any global state.
 */
@Injectable({providedIn: 'root'})
export class CommonParamsService {
  private readonly document = inject(DOCUMENT);

  /** Immutable record of the active common query parameters. */
  private readonly commonParams = parseCommonQueryParams(
    this.document.defaultView?.location.search ?? '',
  );

  /**
   * Returns the active common query parameters captured at SPA bootstrap.
   *
   * @return Immutable record of the active common query parameters (e.g.
   *     {'debug': 'true'}), or an empty record if none is active.
   */
  getCommonParams(): Readonly<Record<string, string>> {
    return this.commonParams;
  }
}
