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
 *
 * @fileoverview Defines the public interface of the navigation strategies
 * between MTT UI2 and the embedded LabConsole (MHFE V6) pages.
 */

export {DeviceDetailNavigationStrategy} from './device_detail_navigation_strategy';
export {HostDetailNavigationStrategy} from './host_detail_navigation_strategy';
export {NavigationStrategyRegistry} from './navigation_strategy_registry';
export {
  EMBEDDED_MODE_PARAM,
  EntityType,
  MessagePage,
  PageNavigationStrategy,
  toQueryParamValues,
} from './page_navigation_strategy';
export type {
  IframeQueryParamsOptions,
  PageSpecificParamDefinition,
  ParamExtractorFn,
  QueryParamsInput,
  ResolvedQueryParams,
  V6PageType,
} from './page_navigation_strategy';
export {SearchNavigationStrategy} from './search_navigation_strategy';
export type {SearchPageConfig} from './search_navigation_strategy';
export {V6NavigationService} from './v6_navigation_service';
