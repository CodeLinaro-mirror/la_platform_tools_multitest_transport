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
  NgZone,
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

import {HeaderSlotService} from './header_slot_service';
import {EntityType, MessagePage, V6NavigationService} from './navigation';

// Re-exported for the existing callers importing them from this file.
export {EntityType, MessagePage};

/** Message sent to the iframe with the geometry of the app header slot. */
export const EMBEDDED_HEADER_SLOT_MESSAGE = 'EMBEDDED_HEADER_SLOT';
/** Message sent by the iframe to (re-)request the header slot geometry. */
export const EMBEDDED_HEADER_SLOT_REQUEST_MESSAGE =
  'EMBEDDED_HEADER_SLOT_REQUEST';
/** Class set on the iframe while it paints into the app header slot. */
export const HEADER_SEARCH_MODE_CLASS = 'header-search-mode';

/** Messages this container sends to the Lab Console iframe. */
type IframeMessage =
  | {type: 'NAVIGATE'; url: string}
  | {type: 'GET_EXTERNAL_URL_RESPONSE'; requestId: string; url: string}
  | {
      type: typeof EMBEDDED_HEADER_SLOT_MESSAGE;
      left: number;
      width: number;
      height: number;
      borderColor: string;
    };

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

    iframe {
      border: none;
      height: 100%;
      width: 100%;
    }

    /*
     * Lab Console search pages: the iframe covers the area from the top of the
     * viewport to the bottom of this container and is clipped (see
     * updateHeaderSlotLayout) to the app header slot and the content area, so
     * that the Lab Console can paint its search input into the app header.
     */
    iframe.header-search-mode {
      position: fixed;
      top: 0;
      z-index: 2;
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
  private readonly headerSlotService = inject(HeaderSlotService);
  private readonly ngZone = inject(NgZone);
  private readonly hostElement = inject<ElementRef<HTMLElement>>(ElementRef);

  private iframeRef?: ElementRef<HTMLIFrameElement>;
  private resizeObserver?: ResizeObserver;
  private layoutFrame = 0;
  /** Last header slot geometry sent to the iframe, as a comparable key. */
  private lastPostedSlot = '';

  @ViewChild('iframe')
  set iframe(ref: ElementRef<HTMLIFrameElement> | undefined) {
    this.iframeRef = ref;
    this.lastPostedSlot = '';
    this.scheduleHeaderSlotLayoutUpdate();
  }
  get iframe(): ElementRef<HTMLIFrameElement> | undefined {
    return this.iframeRef;
  }

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
      this.postMessageToIframe({
        type: 'NAVIGATE',
        url: parsedUrl.pathname + parsedUrl.search,
      });
    }
  }

  /**
   * Posts a message to the Lab Console iframe.
   *
   * @param message The message to send.
   * @param target The window to post to. Defaults to the iframe's content
   *     window; responses are posted back to the window that sent the request.
   *
   * Explanation:
   * Single place for all messages to the iframe, so that they share the same
   * target origin: the iframe is served from this app's origin.
   */
  private postMessageToIframe(
    message: IframeMessage,
    target: Window | null | undefined = this.iframeRef?.nativeElement
      .contentWindow,
  ): void {
    target?.postMessage(message, window.location.origin);
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

    // Keep the iframe geometry in sync with the page: the layout differs
    // between search pages (iframe painting into the app header slot) and
    // detail pages, and the header slot moves/resizes with the window, the
    // side navigation and the header actions.
    this.router.events
      .pipe(
        filter((e): e is NavigationEnd => e instanceof NavigationEnd),
        takeUntil(this.destroy),
      )
      .subscribe(() => {
        this.scheduleHeaderSlotLayoutUpdate();
      });
    this.headerSlotService.slotElement$
      .pipe(takeUntil(this.destroy))
      .subscribe((slot) => {
        this.observeLayoutChanges(slot);
        this.scheduleHeaderSlotLayoutUpdate();
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
    this.resizeObserver?.disconnect();
    if (this.layoutFrame) {
      cancelAnimationFrame(this.layoutFrame);
    }
    this.destroy.next();
    this.destroy.complete();
  }

  /**
   * Watches the elements whose size determines the iframe geometry.
   *
   * @param slot The app header slot element, or null if there is none.
   *
   * Explanation:
   * A ResizeObserver on this container (window resizes, side navigation
   * expanding / collapsing) and on the header slot (header actions appearing
   * or disappearing) re-runs the layout outside the Angular zone, as it only
   * touches the iframe's inline style and posts a message.
   */
  private observeLayoutChanges(slot: HTMLElement | null): void {
    this.resizeObserver?.disconnect();
    this.resizeObserver = undefined;
    // ResizeObserver is a browser API that is missing in some environments
    // (e.g. non-browser test runners). Without it the layout still updates on
    // navigation and header slot changes, just not on resizes.
    if (typeof ResizeObserver === 'undefined') {
      return;
    }
    this.ngZone.runOutsideAngular(() => {
      this.resizeObserver = new ResizeObserver(() => {
        this.scheduleHeaderSlotLayoutUpdate();
      });
      this.resizeObserver.observe(this.hostElement.nativeElement);
      if (slot) {
        this.resizeObserver.observe(slot);
      }
    });
  }

  /** Coalesces layout updates into one per animation frame. */
  private scheduleHeaderSlotLayoutUpdate(): void {
    // `layoutFrame` is the id of an animation frame that is already scheduled
    // and has not run yet: a burst of triggers (ResizeObserver, navigation,
    // slot changes) then results in a single layout update, right before the
    // browser paints the next frame. requestAnimationFrame is missing in some
    // environments (e.g. non-browser test runners).
    if (this.layoutFrame || typeof requestAnimationFrame === 'undefined') {
      return;
    }
    this.ngZone.runOutsideAngular(() => {
      this.layoutFrame = requestAnimationFrame(() => {
        this.layoutFrame = 0;
        this.updateHeaderSlotLayout();
      });
    });
  }

  /**
   * Lays the iframe out for the current page and tells the Lab Console where
   * the app header slot is.
   *
   * @param forcePost Whether to send the slot geometry even if unchanged (e.g.
   *     when the iframe asked for it).
   *
   * Explanation:
   * On the Lab Console search pages the iframe is positioned over the area
   * from the top of the viewport down to the bottom of this container and
   * clipped to (a) the app header slot and (b) the content area below the app
   * header. The Lab Console renders a header band with its docked search input
   * at the slot position (EMBEDDED_HEADER_SLOT message), so the input appears
   * inside the app header while ☰, logo, "Legacy UI" and "Set Default Service
   * Account" remain regular UI2 elements (the clipped parts of the iframe are
   * neither painted nor hit-tested). On detail pages the iframe simply fills
   * this container below the app header.
   */
  updateHeaderSlotLayout(forcePost = false): void {
    const iframe = this.iframeRef?.nativeElement;
    if (!iframe) {
      console.log(
        'Lab Console iframe is not rendered, skipping the header slot layout.',
      );
      return;
    }
    const slot = this.headerSlotService.slotElement$.value;
    if (this.isDetailPage || !slot) {
      if (iframe.classList.contains(HEADER_SEARCH_MODE_CLASS)) {
        iframe.classList.remove(HEADER_SEARCH_MODE_CLASS);
        // Back in the normal flow the iframe must take its size from the
        // stylesheet again (width / height: 100% of this container). The
        // inline geometry below was computed for the fixed-position header
        // search mode (viewport coordinates measured on the search page), and
        // inline styles win over the stylesheet, so leaving them in place
        // would mis-size the iframe on the detail page.
        iframe.style.removeProperty('left');
        iframe.style.removeProperty('width');
        iframe.style.removeProperty('height');
        iframe.style.removeProperty('clip-path');
      }
      return;
    }

    // case for search apge.

    // Geometry in iframe pixels: the iframe is fixed at the top of the
    // viewport (top: 0) and starts at the left edge of this container, so
    // x = viewportX - host.left and y = viewportY.
    // the host element is the NOT the iframe itself, but the iframe's parent container.
    // It's the current Component's host element.
    const host = this.hostElement.nativeElement.getBoundingClientRect();
    const slotRect = slot.getBoundingClientRect();
    // The app header is everything above this container.
    // Since the host is NOT position fixed, the host's top is the app header height.
    const headerHeight = Math.max(0, Math.round(host.top));
    const width = Math.round(host.width);
    // From the top of the viewport down to the bottom of this container.
    // DomRect.bottom = top(headerHeight) + "hostElement's height"
    // so this is the height of the iframe, as iframe needs to be
    // top extended out of the host element, up to the top of the viewport,
    // and the extended part is to show in the app header slot.
    const height = Math.round(host.bottom);
    // Header slot column in iframe x. The slot (a toolbar flex item) and this
    // container are laid out independently, so the slot can stick out of the
    // container horizontally: it starts left of the container when the side
    // navigation is wider than the ☰ button + logo, and it ends right of the
    // container when the content area is narrower than the toolbar (e.g. a
    // vertical scrollbar). The clip polygon and the V6 header band only exist
    // inside the iframe box, whose valid x range is [0, width], so both edges
    // are clamped to that range.
    const slotLeft = Math.min(
      width,
      Math.max(0, Math.round(slotRect.left - host.left)),
    );
    // Never left of slotLeft: a negative slot width would make the polygon
    // self-intersecting and the `width` in the message negative (V6 rejects
    // that); a collapsed slot ends up as a 0px column instead.
    const slotRight = Math.min(
      width,
      Math.max(slotLeft, Math.round(slotRect.right - host.left)),
    );

    iframe.classList.add(HEADER_SEARCH_MODE_CLASS);
    iframe.style.left = `${Math.round(host.left)}px`;
    iframe.style.width = `${width}px`;
    iframe.style.height = `${height}px`;
    // Visible area = the slot column inside the header + the whole content
    // area below the header (an upside-down "T"), as a clockwise polygon
    // starting at the bottom-left corner of the header.
    iframe.style.clipPath =
      `polygon(0 ${headerHeight}px, ${slotLeft}px ${headerHeight}px, ` +
      `${slotLeft}px 0, ${slotRight}px 0, ${slotRight}px ${headerHeight}px, ` +
      `${width}px ${headerHeight}px, ${width}px ${height}px, 0 ${height}px)`;

    const toolbar = slot.closest('mat-toolbar') ?? slot;
    const message: IframeMessage = {
      type: EMBEDDED_HEADER_SLOT_MESSAGE,
      left: slotLeft,
      width: slotRight - slotLeft,
      height: headerHeight,
      borderColor: getComputedStyle(toolbar).borderBottomColor,
    };
    const key = JSON.stringify(message);
    if (forcePost || key !== this.lastPostedSlot) {
      this.lastPostedSlot = key;
      this.postMessageToIframe(message);
    }
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
      this.postMessageToIframe(
        {type: 'GET_EXTERNAL_URL_RESPONSE', requestId, url: absoluteUrl},
        event.source as Window,
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
    } else if (data.type === EMBEDDED_HEADER_SLOT_REQUEST_MESSAGE) {
      this.updateHeaderSlotLayout(/* forcePost= */ true);
    } else {
      console.error('Unknown message type:', data.type, data);
    }
  }
}
