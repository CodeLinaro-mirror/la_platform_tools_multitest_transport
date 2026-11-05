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

import {inject, Injectable} from '@angular/core';
import {TrustedResourceUrl} from 'safevalues';

import {APP_DATA} from '../../services/app_data';
import {CommonParamsService} from '../../services/common_params_service';
import {NavigationTarget} from '../../services/navigation_event_service';

import {NavigationStrategyRegistry} from './navigation_strategy_registry';
import {EntityType, QueryParamsInput} from './page_navigation_strategy';

/** Entity type of the search page of each left navigation menu target. */
const NAVIGATION_TARGET_ENTITY_TYPES: Readonly<
  Record<NavigationTarget, EntityType>
> = {
  [NavigationTarget.DEVICES]: EntityType.DEVICES,
  [NavigationTarget.HOSTS]: EntityType.HOSTS,
};

/**
 * Service orchestrating the navigation between MTT UI2 and the embedded
 * LabConsole (MHFE V6) iframe.
 *
 * It combines the common query parameters captured by CommonParamsService, the
 * APP_DATA flags, and the page strategies looked up from the
 * NavigationStrategyRegistry, so that V6IframeContainerComponent only deals
 * with the view: binding the iframe URL and exchanging messages with the
 * iframe.
 */
@Injectable({providedIn: 'root'})
export class V6NavigationService {
  private readonly appData = inject(APP_DATA);
  private readonly commonParamsService = inject(CommonParamsService);

  /**
   * Checks whether the embedded LabConsole page of an entity is enabled.
   *
   * @param type The entity type (hosts or devices).
   * @param id The optional entity ID (if provided, checks the detail page).
   * @return True if the page is enabled, false otherwise.
   *
   * Explanation:
   * The search pages are enabled by enableLabConsoleSearchPage, while the
   * detail pages are enabled by enableLabConsoleUI.
   */
  isEntityPageEnabled(type: EntityType, id?: string): boolean {
    const strategy = NavigationStrategyRegistry.forEntity(type, id);
    return strategy.isEnabled(this.appData);
  }

  /**
   * Builds the initial `src` URL of the iframe for an entity page.
   *
   * @param type The entity type (hosts or devices).
   * @param id The optional entity ID (if provided, builds the detail page).
   * @param routeParams The query parameters of the current MTT URL.
   * @return The iframe URL, forwarding the allowed query parameters and setting
   *     is_embedded_mode=true.
   */
  buildInitialIframeUrl(
    type: EntityType,
    id: string | undefined,
    routeParams: QueryParamsInput,
  ): TrustedResourceUrl {
    const strategy = NavigationStrategyRegistry.forEntity(type, id);
    return strategy.buildInitialIframeUrl(
      id,
      routeParams,
      this.commonParamsService.getCommonParams(),
    );
  }

  /**
   * Builds the URL to navigate the already loaded iframe to an entity page.
   *
   * @param type The entity type (hosts or devices).
   * @param id The optional entity ID (if provided, builds the detail page).
   * @param routeParams The query parameters of the current MTT URL.
   * @return The URL, forwarding the allowed query parameters and setting
   *     is_embedded_mode=true.
   */
  buildEntityIframeNavigateUrl(
    type: EntityType,
    id: string | undefined,
    routeParams: QueryParamsInput,
  ): string {
    const strategy = NavigationStrategyRegistry.forEntity(type, id);
    return strategy.buildIframeNavigateUrl(
      id,
      routeParams,
      this.commonParamsService.getCommonParams(),
    );
  }

  /**
   * Builds the URL to reset the search page of the iframe, when the user
   * clicks the left navigation menu item of the current search page.
   *
   * @param target The left navigation menu target (e.g. DEVICES or HOSTS).
   * @param currentParams The query parameters of the current MTT URL.
   * @return The URL of the search page, without the search query parameters
   *     (e.g. f, gb) but with the common query parameters (e.g. debug) and
   *     is_embedded_mode=true.
   */
  buildSearchResetIframeUrl(
    target: NavigationTarget,
    currentParams: QueryParamsInput,
  ): string {
    const strategy = NavigationStrategyRegistry.forEntity(
      NAVIGATION_TARGET_ENTITY_TYPES[target],
    );
    return strategy.buildIframeNavigateUrl(
      undefined,
      currentParams,
      this.commonParamsService.getCommonParams(),
      {resetPageSpecificParams: true},
    );
  }

  /**
   * Resolves the absolute MTT URL of the page requested by a GET_EXTERNAL_URL
   * message of the iframe (e.g. to open a link in a new browser tab).
   *
   * @param page The page name of the message (e.g. 'host_details').
   * @param messageParams The `params` of the message.
   * @param origin The origin of MTT (e.g. window.location.origin).
   * @return The absolute URL, carrying the common query parameters.
   */
  resolveExternalUrl(
    page: string,
    messageParams: QueryParamsInput,
    origin: string,
  ): string {
    return `${origin}${this.resolveNavigatedParentUrl(page, messageParams)}`;
  }

  /**
   * Resolves the MTT URL to navigate to, when the iframe notifies with a
   * NAVIGATED message that it navigated to another page.
   *
   * @param page The page name of the message (e.g. 'device_details').
   * @param messageParams The `params` of the message.
   * @return The URL relative to the MTT origin, carrying the common query
   *     parameters.
   */
  resolveNavigatedParentUrl(
    page: string,
    messageParams: QueryParamsInput,
  ): string {
    const strategy = NavigationStrategyRegistry.forExternalMessagePage(page);
    return strategy.buildParentUrl(
      strategy.extractEntityId(messageParams),
      this.commonParamsService.getCommonParams(),
    );
  }

  /**
   * Resolves the query parameters of the MTT URL, when the iframe notifies with
   * a SEARCH_STATE_CHANGED message that its search state changed.
   *
   * @param searchParams The `params` of the message (e.g. f, gb).
   * @return The common query parameters merged with the search parameters.
   */
  resolveSearchStateParentQueryParams(
    searchParams: QueryParamsInput,
  ): Record<string, unknown> {
    return {...this.commonParamsService.getCommonParams(), ...searchParams};
  }
}
