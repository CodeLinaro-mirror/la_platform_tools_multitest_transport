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

import {
  NavigationEventService,
  NavigationTarget,
} from '../services/navigation_event_service';
import {PreferenceService} from '../services/preference_service';

import {EntityType, MessagePage, V6NavigationService} from './navigation';

// Re-exported for the existing callers importing them from this file.
export {EntityType, MessagePage};

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
  readonly preferenceService = inject(PreferenceService);
  protected readonly navigationEventService = inject(NavigationEventService);
  private readonly v6NavigationService = inject(V6NavigationService);

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
   * If the target LabConsole page is enabled, asks V6NavigationService for the
   * iframe URL based on type and ID, which forwards the allowed current query
   * params and sets is_embedded_mode=true.
   * Calls iframeNavigate asynchronously.
   */
  navigateForEntity(type: EntityType, id?: string): void {
    if (this.v6NavigationService.isEntityPageEnabled(type, id)) {
      Promise.resolve().then(() => {
        const url = this.v6NavigationService.buildEntityIframeNavigateUrl(
          type,
          id,
          this.route.snapshot?.queryParams || {},
        );
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
    // UI2 URL is reset (query parameters stripped, except the common ones such
    // as debug). We explicitly command the
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
   * the search query parameters (f, gb) while retaining the common
   * query parameters (e.g. debug, fake_data) and setting is_embedded_mode=true.
   *
   * @param target The navigation target page (e.g. DEVICES or HOSTS).
   * @return void
   *
   * Explanation:
   * Extracts current query parameters, asks V6NavigationService for the clean
   * root list URL (without search-specific filters, with the persistent query
   * parameters), and commands the iframe to navigate to it.
   */
  private navigateForSearchReset(target: NavigationTarget): void {
    const currentParams = {
      ...this.router.parseUrl(this.router.url).queryParams,
      ...(this.route.snapshot?.queryParams || {}),
    };
    this.iframeNavigate(
      this.v6NavigationService.buildSearchResetIframeUrl(target, currentParams),
    );
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
   * If iframeUrl is not set, it asks V6NavigationService for the initial
   * TrustedResourceUrl of the iframe, which appends the allowed query params
   * and sets is_embedded_mode=true.
   * If iframeUrl is already set, it calls navigateForEntity to trigger navigation.
   */
  initIframeUrl(type: EntityType, id?: string): void {
    if (this.iframeUrl) {
      // Container already initialized, tell iframe to navigate
      this.navigateForEntity(type, id);
    } else {
      this.iframeUrl = this.v6NavigationService.buildInitialIframeUrl(
        type,
        id,
        this.route.snapshot?.queryParams || {},
      );
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
      const absoluteUrl = this.v6NavigationService.resolveExternalUrl(
        page,
        params,
        window.location.origin,
      );
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
        queryParams:
          this.v6NavigationService.resolveSearchStateParentQueryParams(params),
      });
    } else if (data.type === 'NAVIGATED') {
      const {page, params} = data;
      const fullUrl = this.v6NavigationService.resolveNavigatedParentUrl(
        page,
        params,
      );
      this.router.navigateByUrl(fullUrl);
    }
  }
}
