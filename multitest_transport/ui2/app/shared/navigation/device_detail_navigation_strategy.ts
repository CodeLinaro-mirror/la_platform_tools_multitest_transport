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

import {AppData} from '../../services/app_data';

import {
  EntityType,
  MessagePage,
  PageNavigationStrategy,
  PageSpecificParamDefinition,
  QueryParamsInput,
} from './page_navigation_strategy';

/**
 * Navigation strategy of the LabConsole device detail page (`/devices/:id`),
 * which is enabled by the enableLabConsoleUI AppData flag.
 */
export class DeviceDetailNavigationStrategy extends PageNavigationStrategy {
  readonly pageType = 'device_detail' as const;
  readonly entityType = EntityType.DEVICES;
  readonly isDetailPage = true;
  override readonly externalMessagePage = MessagePage.DEVICE_DETAILS;
  /** Search query params (e.g. f, gb) are never forwarded to detail pages. */
  readonly pageSpecificParams: Readonly<
    Record<string, PageSpecificParamDefinition>
  > = {};

  isEnabled(appData: AppData | null | undefined): boolean {
    return Boolean(appData?.enableLabConsoleUI);
  }

  buildRoutePath(id?: string): string {
    return `/devices/${this.requireId(id)}`;
  }

  buildIframeBaseUrl(id?: string): TrustedResourceUrl {
    return trustedResourceUrl`/labui/devices/${this.requireId(id)}`;
  }

  /** Resolves the device ID from the `device_uuid` (or `uuid`) param, if any. */
  override extractEntityId(messageParams: QueryParamsInput): string | undefined {
    const id = messageParams['device_uuid'] || messageParams['uuid'];
    return id == null ? undefined : String(id);
  }
}
