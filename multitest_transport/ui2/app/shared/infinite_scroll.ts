/**
 * Copyright 2019 Google LLC
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

/**
 * This file is referenced from android/video/brimstone/frontend/app/
 * infinite_scroll/infinite_scroll.ts
 */

import {DOCUMENT} from '@angular/common';
import {Directive, ElementRef, EventEmitter, Inject, Input, NgZone, OnChanges, OnDestroy, OnInit, Output, SimpleChanges} from '@angular/core';
import {BehaviorSubject, fromEvent, merge, Subject} from 'rxjs';
import {debounceTime, filter, skip, takeUntil} from 'rxjs/operators';

const DEFAULT_DEBOUNCE_TIME_MS = 200;
const DEFAULT_THRESHOLD_PCT = 75;

/**
 * Directive for implementing an infinite scroll UI.
 *
 * The InfiniteScroll directive is agnostic of what the underlying component or
 * element is; it only needs to be attached to a scrollable element. The
 * scrollable component must handle the `scrollLoad` event and replace its
 * `completed` promise with one that resolves when the loading is completed.
 *
 * The scrolling threshold is based on a percentage of the container height, and
 * not a precise pixel height, because the size of content may not be known in
 * advance, and this approach scales to different container heights without
 * requiring advance calculations of offsets. Using the container height instead
 * of content height also provides consistent behavior in terms of how much
 * content remains to be scrolled before triggering a new load, e.g. it will not
 * change based on how much content is already loaded/scrolled past.
 */
@Directive({standalone: false,
            selector: '[mttInfiniteScroll]'})
export class InfiniteScroll implements OnChanges, OnInit, OnDestroy {
  /**
   * Provides a way to control the initial enabled state of the scroll. When the
   * directive is first created, it has no prior history of requests and
   * therefore does not know whether or not more data can be loaded. By default,
   * it will assume that more data exists. This can be overridden if this
   * property has a value of `false` during initialization.
   */
  @Input() enableInfiniteScroll = true;

  /**
   * Specifies throttling of scroll events, in milliseconds.
   *
   * This is used to prevent slowdowns due to checking scroll properties (and
   * thus triggering forced synchronous layouts) on every scroll. The value
   * specified here will be the minimum time between forced layouts, as well as
   * the maximum time a user might have to wait before a scroll actually
   * triggers loading.
   */
  @Input() scrollDebounceTimeMs = DEFAULT_DEBOUNCE_TIME_MS;

  /** Event emitted when the element has scrolled enough to need new content. */
  @Output() readonly scrollLoad = new EventEmitter<InfiniteScrollLoadEvent>();

  /**
   * Target element to which to apply the scrolling behavior. This property is
   * read only once at initialization; subsequent changes will have no effect.
   */
  // tslint:disable-next-line:no-input-rename Directive name is the input name.
  @Input('mttInfiniteScroll') scrollTarget = InfiniteScrollTarget.SELF;

  /**
   * The minimum distance from the bottom of the content, expressed as a
   * percentage of the total container height, which the scrolled distance must
   * exceed in order to trigger a new load.
   *
   * For example, given these values:
   * - Threshold (%): 75
   * - Container height: 200px
   * - Content height: 1000px
   *
   * Threshold * container height yields 150px. Subtracting from the end of the
   * content, we get 1000px - 150px = 850px. The next load will be triggered
   * when the BOTTOM of the scroll position is >= 850px, which corresponds to
   * a `scrollTop` of 850px - 200px = 650px.
   *
   * The actual threshold is always based on the container height, not the
   * content height or an arbitrarily-chosen dimension. One way to think of this
   * is: in the example above, if we are displaying a table that is 1000px high,
   * and every row is exactly 50px, a content load will always be triggered just
   * after the third-to-last row starts scrolling into view.
   */
  @Input() scrollThreshold = DEFAULT_THRESHOLD_PCT;

  private readonly destroyed = new Subject<void>();
  private hasMoreContent = false;
  private isLoading = false;
  private readonly loading = new BehaviorSubject(false);

  constructor(
      private readonly element: ElementRef,
      @Inject(DOCUMENT) private readonly document: Document,
      private readonly zone: NgZone) {}

  /**
   * Handles changes to component bindings.
   * @param changes Latest changes.
   */
  ngOnChanges(changes: SimpleChanges) {
    if ('enableInfiniteScroll' in changes) {
      this.hasMoreContent = this.enableInfiniteScroll;
    }
  }

  /** Cleans up resources used by the component. */
  ngOnDestroy() {}

  /** Handles component initialization. */
  ngOnInit() {
    // Set whether current page has more content can be loaded
    this.hasMoreContent = this.enableInfiniteScroll;
    // Set the current isLoading state
    this.loading.subscribe((isLoading) => {
      this.isLoading = isLoading;
    });

    // Listeners should be installed from outside the Angular zone in order to
    // prevent a change-detection cycle from being triggered every time the
    // event fires. We'll manually fire change detection when a load starts and
    // completes.
    this.zone.runOutsideAngular(() => {
      this.installScrollListener();
    });
  }

  /**
   * Allow targeted element's scroll event to be detected and fire load content
   * event accordingly
   */
  private installScrollListener() {
    const target = this.scrollTarget === InfiniteScrollTarget.DOCUMENT ?
        this.document :
        this.element.nativeElement;
    const scrollable = this.scrollTarget === InfiniteScrollTarget.DOCUMENT ?
        this.document.scrollingElement as HTMLElement ||
            this.document.documentElement :
        this.element.nativeElement as HTMLElement;
    const scrollEvents = fromEvent(target, 'scroll');
    const loadCompletedEvents = this.loading.pipe(
        filter((isLoading) => !isLoading),
        // First event is just the default value, not a transition.
        skip(1));
    merge(loadCompletedEvents, scrollEvents)
        .pipe(
            takeUntil(this.destroyed),
            debounceTime(this.scrollDebounceTimeMs),
            // If isloading is false, now we want to start a loading event
            // If isloading is true, we want to wait till that event is finished
            filter(() => !this.isLoading && this.hasMoreContent),
            filter(() => this.isOverScrollThreshold(scrollable)),
            )
        .subscribe(() => {
          // On fire loading event, we want to set isLoading to true
          this.loading.next(true);
          const loadEvent = new InfiniteScrollLoadEvent();
          this.zone.run(() => {
            // emit loading event
            this.scrollLoad.emit(loadEvent);
            // the listeners on loadEvent will change the completed Promise
            // and pass back whether the current loading page has more content
            loadEvent.completed.then((hasMoreContent) => {
              this.hasMoreContent = hasMoreContent;
              // on event loaded, set isLoading to false
              this.loading.next(false);
            });
          });
        });
  }
  /**
   * Check whether we have scrolled over the Threshold which will determine
   * whether later we would need to load more content
   * @param element the scrolling element
   * @return boolean
   */
  private isOverScrollThreshold(element: HTMLElement): boolean {
    const thresholdPx = this.scrollThreshold / 100 * element.clientHeight;
    const maxScrollBottomPx = element.scrollHeight - thresholdPx;
    return element.scrollTop + element.clientHeight >= maxScrollBottomPx;
    // return false;
  }
}

/** Defines available targets for an infinite scroll directive. */
export enum InfiniteScrollTarget {
  /** Apply behavior to the specific element with the directive. */
  SELF = 'self',

  /**
   * Apply behavior to the document (body), regardless of which element the
   * directive is attached to.
   */
  DOCUMENT = 'document'
}

/** Data for an infinite-scroll loading event. */
export class InfiniteScrollLoadEvent {
  /**
   * Promise that resolves when the data is finished loading. The boolean
   * parameter indicates whether or not more data is available in addition to
   * what was just loaded.
   */
  completed = Promise.resolve(false);
}
