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

import {Portal} from '@angular/cdk/portal';
import {Injectable} from '@angular/core';
import {BehaviorSubject} from 'rxjs';

/**
 * Shares the app header's content slot (the free area between the logo and
 * the header actions) with the routed pages.
 *
 * Pages project content into the slot (e.g. the device / host detail pages
 * render their back button, breadcrumb and entity switcher there instead of a
 * sub-header), and the V6 iframe container measures the slot element so that
 * the embedded Lab Console can paint its search input exactly into it.
 */
@Injectable({providedIn: 'root'})
export class HeaderSlotService {
  /** Content currently projected into the header slot, or null if none. */
  readonly portal$ = new BehaviorSubject<Portal<unknown>|null>(null);

  /** The slot element of the app header, once the app component registered it. */
  readonly slotElement$ = new BehaviorSubject<HTMLElement|null>(null);

  /**
   * Registers the slot element rendered by the app header.
   *
   * @param element The slot element, or null when the header is destroyed.
   */
  setSlotElement(element: HTMLElement|null) {
    this.slotElement$.next(element);
  }

  /** Returns whether an app header slot is available on this page. */
  isAvailable(): boolean {
    return this.slotElement$.value !== null;
  }

  /**
   * Projects the given content into the header slot, replacing any previous
   * content.
   *
   * @param portal The content to render in the slot.
   */
  attach(portal: Portal<unknown>) {
    if (this.portal$.value !== portal) {
      this.portal$.next(portal);
    }
  }

  /**
   * Clears the header slot.
   *
   * @param portal When given, the slot is only cleared if it currently shows
   *     this content, so that a page being destroyed does not remove the
   *     content a newly activated page has just attached.
   */
  detach(portal?: Portal<unknown>) {
    if (!portal || this.portal$.value === portal) {
      this.portal$.next(null);
    }
  }
}
