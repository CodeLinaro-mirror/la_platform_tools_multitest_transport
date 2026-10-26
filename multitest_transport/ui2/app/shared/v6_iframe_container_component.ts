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

import {CommonModule} from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  HostListener,
  inject,
  OnDestroy,
  OnInit,
  ViewChild,
} from '@angular/core';
import {SafeResourceUrl} from '@angular/platform-browser';
import {
  ActivatedRoute,
  NavigationEnd,
  Router,
  RouterModule,
} from '@angular/router';
import {combineLatest, ReplaySubject} from 'rxjs';
import {filter, map, startWith, takeUntil} from 'rxjs/operators';
import {appendParams, TrustedResourceUrl, trustedResourceUrl} from 'safevalues';

import {APP_DATA} from '../services/app_data';
import {
  NavigationEventService,
  NavigationTarget,
} from '../services/navigation_event_service';
import {PreferenceService} from '../services/preference_service';

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
 * Search-page-only query parameters that should not be forwarded to detail pages.
 */
export const SEARCH_QUERY_PARAMS_TO_REMOVE = new Set(['f', 'gb', 'fleet', 'q']);

/**
 * Query parameters that are allowed in the iframe, which means ONLY these
 * params will be forwarded to the iframe.
 * Note: for detail pages, only
 *  ALLOWED_QUERY_PARAMS - SEARCH_QUERY_PARAMS_TO_REMOVE
 * will be forwarded.
 */
export const ALLOWED_QUERY_PARAMS = new Set([
  'f', // the filter
  'gb', // the group by
  // 'fleet', // fleet is NOT supported in OSS
  // 'q', // the query text. This is useless as it's the tmp status.
  'is_embedded_mode',
  // 'universe', // universe is NOT supported in OSS
  'fake_data',
  'debug',
]);

/**
 * Determines whether a query parameter should be forwarded to the iframe.
 *
 * @param key The query parameter key.
 * @param isDetail Whether the destination is a detail page or performing a search reset.
 * @return True if the parameter is allowed, false otherwise.
 *
 * Explanation:
 * Validates the query parameter against ALLOWED_QUERY_PARAMS. If navigating to
 * a detail page or performing a search reset, search-specific parameters
 * (gb, q) are filtered out so they are not carried over.
 */
export function isAllowedQueryParam(key: string, isDetail = false): boolean {
  if (!ALLOWED_QUERY_PARAMS.has(key)) {
    return false;
  }
  if (isDetail && SEARCH_QUERY_PARAMS_TO_REMOVE.has(key)) {
    return false;
  }
  return true;
}

/**
 * Initial query parameters that should persist in memory across client-side
 * SPA navigations and be appended to iframe navigations.
 */
export const ALLOWED_INITIAL_PERSISTENT_PARAMS = new Set([
  'debug',
  'fake_data',
]);

/**
 * Parses query parameters from a search string (defaulting to window.location.search)
 * and captures allowed persistent parameters where the value is 'true' or '1'.
 *
 * @param searchStr Optional search string (e.g., '?debug=true&fake_data=1').
 * @return Record of key-value pairs for allowed persistent query parameters.
 *
 * Explanation:
 * Extracts persistent query flags (e.g. debug, fake_data) from the initial URL search
 * string so they can be retained and forwarded across iframe navigations during the session.
 */
export function captureInitialPersistentQueryParams(
  searchStr?: string,
): Record<string, string> {
  const result: Record<string, string> = {};
  const search =
    searchStr !== undefined
      ? searchStr
      : typeof window !== 'undefined' && window.location
        ? window.location.search
        : '';
  if (!search) {
    return result;
  }
  const searchParams = new URLSearchParams(search);
  for (const [key, value] of searchParams.entries()) {
    if (ALLOWED_INITIAL_PERSISTENT_PARAMS.has(key)) {
      // Only when it's string "true" or string "1", treat as true
      if (value === 'true' || value === '1') {
        result[key] = value;
      }
    }
  }
  return result;
}

/**
 * In-memory store for initial persistent query parameters captured at page visit time.
 * Lives in module scope for the tab's lifetime, surviving route changes, but naturally
 * resets on hard refresh (Ctrl+R) and does not leak across tabs.
 */
let initialPersistentQueryParams: Record<string, string> =
  captureInitialPersistentQueryParams();

/**
 * Helper to update or reset the persistent query parameters (useful for unit testing).
 *
 * @param params Record of persistent parameter key-value pairs to set.
 * @return void
 *
 * Explanation:
 * Replaces the module-scoped persistent query parameters with the provided record.
 */
export function setInitialPersistentQueryParams(
  params: Record<string, string>,
): void {
  initialPersistentQueryParams = {...params};
}

/**
 * Shared container for V6 iframe pages in UI2.
 * This component persists across Host and Device detail pages,
 * allowing the iframe to remain alive during client-side navigation.
 */
@Component({
  changeDetection: ChangeDetectionStrategy.Eager,
  standalone: true,
  imports: [CommonModule, RouterModule],
  selector: 'v6-iframe-container',
  templateUrl: './v6_iframe_container_component.ng.html',
  styles: [
    `
    :host {
      display: flex;
      flex-direction: column;
      height: 100%;
    }
  `,
  ],
})
export class V6IframeContainerComponent implements OnInit, OnDestroy {
  protected readonly route = inject(ActivatedRoute);
  protected readonly router = inject(Router);
  readonly appData = inject(APP_DATA);
  readonly preferenceService = inject(PreferenceService);
  protected readonly navigationEventService = inject(NavigationEventService);

  @ViewChild('iframe') iframe?: ElementRef<HTMLIFrameElement>;

  /**
   * Checks if the current page is a detail page.
   *
   * @return True if it is a detail page, false otherwise.
   *
   * Explanation:
   * Inspects the active child route tree for the entity ':id' parameter.
   * Also verifies via URL pattern matching against known entity detail paths
   * (/(hosts|devices)/<id>) so that subdirectory deployments (base href) or path
   * prefixes do not cause false positives.
   */
  get isDetailPage(): boolean {
    // 1. Inspect the active child route tree for the ':id' parameter defined in app.ts
    let child = this.route.snapshot?.firstChild;
    while (child) {
      if (child.paramMap?.has('id') || child.params?.['id']) {
        return true;
      }
      child = child.firstChild;
    }

    // 2. Fallback / supplementary check on router.url for detail pattern /(hosts|devices)/<id>
    const cleanUrl = this.router.url.split('?')[0].split('#')[0];
    return /(?:^|\/)(?:hosts|devices)\/[^/]+/.test(cleanUrl);
  }

  useLabConsoleIframe$ = combineLatest([
    this.router.events.pipe(
      filter((e): e is NavigationEnd => e instanceof NavigationEnd),
      startWith(null),
      map(() => this.isDetailPage),
    ),
    this.preferenceService.useLabConsoleUISubject$,
    this.preferenceService.useLabConsoleSearchPageSubject$,
  ]).pipe(
    map(([isDetail, useDetail, useSearch]) => {
      return isDetail ? useDetail : useSearch;
    }),
  );

  /**
   * Sends a navigation message to the iframe.
   *
   * @param url The URL to navigate to in the iframe.
   * @return void
   *
   * Explanation:
   * Posts a 'NAVIGATE' message to the iframe window with the relative URL.
   */
  iframeNavigate(url: string): void {
    if (this.iframe && this.iframe.nativeElement.contentWindow) {
      const parsedUrl = new URL(url, window.location.origin);
      this.iframe.nativeElement.contentWindow.postMessage(
        {type: 'NAVIGATE', url: parsedUrl.pathname + parsedUrl.search},
        window.location.origin,
      );
    }
  }

  /**
   * Navigates to a specific entity or list in the iframe.
   *
   * @param type The entity type (hosts or devices).
   * @param id The optional entity ID (if provided, navigates to detail page).
   * @return void
   *
   * Explanation:
   * Constructs the URL for the iframe based on type and ID.
   * Forwards current query params and sets is_embedded_mode=true.
   * Calls iframeNavigate asynchronously.
   */
  navigateForEntity(type: EntityType, id?: string): void {
    const isDetail = !!id;
    const isEnabled = isDetail
      ? this.appData?.enableLabConsoleUI
      : this.appData?.enableLabConsoleSearchPage;

    if (isEnabled) {
      Promise.resolve().then(() => {
        let url = isDetail ? `/${type}/${id}` : `/${type}`;
        const queryParams = new URLSearchParams();

        // Forward allowed query params
        const currentParams = this.route.snapshot?.queryParams || {};
        for (const key of Object.keys(currentParams)) {
          if (!isAllowedQueryParam(key, isDetail)) {
            continue;
          }
          queryParams.set(key, currentParams[key]);
        }
        // Merge initial persistent query params (e.g. debug, fake_data) if not present in current route
        for (const [key, value] of Object.entries(
          initialPersistentQueryParams,
        )) {
          if (!queryParams.has(key) && isAllowedQueryParam(key, isDetail)) {
            queryParams.set(key, value);
          }
        }
        queryParams.set('is_embedded_mode', 'true');
        url += '?' + queryParams.toString();

        this.iframeNavigate(url);
      });
    }
  }

  private readonly destroy = new ReplaySubject<void>();

  iframeUrl?: SafeResourceUrl;

  ngOnInit() {
    this.preferenceService.useLabConsoleUISubject$
      .pipe(takeUntil(this.destroy))
      .subscribe((useLabConsoleUI) => {
        if (!useLabConsoleUI) {
          // Clear the iframe URL when LabConsole UI is disabled.
          // So that iframeUrl could be set when user re-enables LabConsole UI.
          this.iframeUrl = undefined;
        }
      });

    // Listen to left navigation menu clicks. When the user clicks the "Devices"
    // or "Hosts" menu item while already on that search/list page, the parent
    // UI2 URL is reset (query parameters stripped). We explicitly command the
    // iframe to navigate to the clean URL to reset its search filters on demand,
    // keeping the iframe in sync with the parent window.
    // Note: Detail pages are excluded, as the original behavior will already navigate to list page, no
    // need to do one more extra navigation.
    this.navigationEventService.navMenuClick$
      .pipe(takeUntil(this.destroy))
      .subscribe((target) => {
        const isSearchPage = !this.isDetailPage;
        if (
          target === NavigationTarget.DEVICES &&
          isSearchPage &&
          this.router.url.startsWith('/devices')
        ) {
          this.navigateForSearchReset(target);
        } else if (
          target === NavigationTarget.HOSTS &&
          isSearchPage &&
          this.router.url.startsWith('/hosts')
        ) {
          this.navigateForSearchReset(target);
        }
      });
  }

  /**
   * Navigates the iframe to the root list URL for the entity, removing
   * any search query parameters (gb, q) while retaining other
   * query parameters and setting is_embedded_mode=true.
   *
   * @param target The navigation target page (e.g. DEVICES or HOSTS).
   * @return void
   *
   * Explanation:
   * Extracts current query parameters, removes search-specific filters, merges persistent
   * query parameters, and commands the iframe to navigate to the clean root list URL.
   */
  private navigateForSearchReset(target: NavigationTarget): void {
    const currentParams = {
      ...this.router.parseUrl(this.router.url).queryParams,
      ...(this.route.snapshot?.queryParams || {}),
    };
    const queryParams = new URLSearchParams();
    for (const key of Object.keys(currentParams)) {
      if (!isAllowedQueryParam(key, /* isDetail= */ true)) {
        continue;
      }
      const val = currentParams[key];
      if (Array.isArray(val)) {
        for (const item of val) {
          queryParams.append(key, String(item));
        }
      } else {
        queryParams.set(key, String(val));
      }
    }
    // Merge initial persistent query params (e.g. debug, fake_data) if not present
    for (const [key, value] of Object.entries(initialPersistentQueryParams)) {
      if (!queryParams.has(key)) {
        queryParams.set(key, value);
      }
    }
    queryParams.set('is_embedded_mode', 'true');
    this.iframeNavigate(`/${target}?${queryParams.toString()}`);
  }

  ngOnDestroy() {
    this.destroy.next();
    this.destroy.complete();
  }

  /**
   * Initializes or updates the iframe URL.
   *
   * @param type The entity type (hosts or devices).
   * @param id The optional entity ID.
   * @return void
   *
   * Explanation:
   * If iframeUrl is not set, it constructs the initial TrustedResourceUrl for the iframe.
   * Appends query params and sets is_embedded_mode=true.
   * If iframeUrl is already set, it calls navigateForEntity to trigger navigation.
   */
  initIframeUrl(type: EntityType, id?: string): void {
    if (this.iframeUrl) {
      // Container already initialized, tell iframe to navigate
      this.navigateForEntity(type, id);
    } else {
      let baseUrl: TrustedResourceUrl;
      if (type === EntityType.HOSTS) {
        baseUrl = id
          ? trustedResourceUrl`/labui/hosts/${id}`
          : trustedResourceUrl`/labui/hosts`;
      } else if (type === EntityType.DEVICES) {
        baseUrl = id
          ? trustedResourceUrl`/labui/devices/${id}`
          : trustedResourceUrl`/labui/devices`;
      } else {
        throw new Error(`Unsupported entity type: ${type}`);
      }

      // Append query params from current MTT URL
      const queryParams = this.route.snapshot?.queryParams || {};
      const paramsToAppend: Record<string, string[]> = {
        'is_embedded_mode': ['true'],
      };
      const isDetail = !!id;
      for (const key of Object.keys(queryParams)) {
        if (!isAllowedQueryParam(key, isDetail)) {
          continue;
        }
        const val = queryParams[key];
        paramsToAppend[key] = Array.isArray(val)
          ? val.map(String)
          : [String(val)];
      }
      // Merge initial persistent query params (e.g. debug, fake_data) if not present
      for (const [key, value] of Object.entries(initialPersistentQueryParams)) {
        if (!paramsToAppend[key]) {
          paramsToAppend[key] = [value];
        }
      }

      this.iframeUrl = appendParams(baseUrl, paramsToAppend);
    }
  }

  /**
   * Handles messages received from the iframe.
   *
   * @param event The MessageEvent received.
   * @return void
   *
   * Explanation:
   * Validates message origin and handles message types:
   * - GET_EXTERNAL_URL: Posts back the external URL to iframe for the requested page.
   * - SEARCH_STATE_CHANGED: Updates the parent router query params when iframe search state changes.
   * - NAVIGATED: Updates the parent router URL when iframe navigates to a new page.
   */
  @HostListener('window:message', ['$event'])
  onMessage(event: MessageEvent): void {
    if (event.origin !== window.location.origin) {
      return;
    }
    const data = event.data;
    if (!data) return;

    if (data.type === 'GET_EXTERNAL_URL') {
      const {requestId, page, params} = data;
      let url = '';
      if (page === MessagePage.HOST_DETAILS) {
        url = `/hosts/${params['host_name']}`;
      } else if (page === MessagePage.DEVICE_DETAILS) {
        url = `/devices/${params['device_uuid'] || params['uuid']}`;
      } else {
        throw new Error(`Unsupported page type in GET_EXTERNAL_URL: ${page}`);
      }

      const persistentParams = new URLSearchParams(
        initialPersistentQueryParams,
      ).toString();
      const fullUrl = persistentParams ? `${url}?${persistentParams}` : url;
      const absoluteUrl = `${window.location.origin}${fullUrl}`;
      (event.source as Window).postMessage(
        {
          type: 'GET_EXTERNAL_URL_RESPONSE',
          requestId,
          url: absoluteUrl,
        },
        {targetOrigin: event.origin},
      );
    } else if (data.type === 'SEARCH_STATE_CHANGED') {
      const {params} = data;
      this.router.navigate([], {
        relativeTo: this.route,
        queryParams: {
          ...initialPersistentQueryParams,
          ...params,
        },
      });
    } else if (data.type === 'NAVIGATED') {
      const {page, params} = data;
      let url = '';
      if (page === MessagePage.HOST_DETAILS) {
        url = `/hosts/${params['host_name']}`;
      } else if (page === MessagePage.DEVICE_DETAILS) {
        url = `/devices/${params['device_uuid'] || params['uuid']}`;
      } else {
        throw new Error(`Unsupported page type in NAVIGATED: ${page}`);
      }

      const persistentParams = new URLSearchParams(
        initialPersistentQueryParams,
      ).toString();
      const fullUrl = persistentParams ? `${url}?${persistentParams}` : url;
      this.router.navigateByUrl(fullUrl);
    }
  }
}
