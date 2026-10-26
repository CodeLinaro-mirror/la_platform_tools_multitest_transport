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

import {Injectable} from '@angular/core';
import {Subject} from 'rxjs';

/** Target pages supported by navigation events. */
export enum NavigationTarget {
  DEVICES = 'devices',
  HOSTS = 'hosts',
}

/**
 * Service to broadcast user navigation events (e.g. left navigation menu clicks)
 * to components so they can reset or synchronize their state on demand.
 */
@Injectable({providedIn: 'root'})
export class NavigationEventService {
  readonly navMenuClick$ = new Subject<NavigationTarget>();

  /**
   * Notifies subscribers that a navigation menu item was clicked.
   *
   * @param target The navigation target page that was clicked (e.g. DEVICES or HOSTS).
   * @return void
   *
   * Explanation:
   * Broadcasts the target event through the navMenuClick$ Subject to notify
   * listeners (such as the V6 iframe container) to handle view reset.
   */
  notifyNavMenuClicked(target: NavigationTarget): void {
    this.navMenuClick$.next(target);
  }
}
