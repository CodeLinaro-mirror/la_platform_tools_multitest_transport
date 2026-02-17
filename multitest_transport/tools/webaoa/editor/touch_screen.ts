/**
 * @license
 * Copyright 2020 Google LLC
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

import {Component, EventEmitter, Output, ChangeDetectionStrategy} from '@angular/core';

import {Point} from '../device/device';
import {AoaAction, ClickAction, SwipeAction} from './action';

/** Max gesture duration that will be considered a click. */
const MAX_CLICK_MILLIS = 100;

/** A device's touchscreen, capable of handling clicks and gestures. */
@Component({
  changeDetection: ChangeDetectionStrategy.Eager,standalone: false,
  selector: 'touch-screen',
  templateUrl: './touch_screen.ng.html',
  styleUrls: ['./touch_screen.css'],
})
export class TouchScreen {
  /** Starting timestamp and position of the current gesture. */
  private startTime?: number;
  private startPoint?: Point;
  /** Current cursor position. */
  currentPoint = new Point(0, 0);
  /** Emits whenever a user clicks or swipes on the screen. */
  @Output() readonly action = new EventEmitter<AoaAction>();

  /** Tracks the current position of the cursor. */
  trackCursor(event: MouseEvent) {
    this.currentPoint = new Point(event.offsetX, event.offsetY);
  }

  /** Starts recording a gesture. */
  startGesture(event: MouseEvent) {
    this.startTime = Date.now();
    this.startPoint = new Point(event.offsetX, event.offsetY);
  }

  /** Completes the current gesture and emits the corresponding action. */
  finishGesture(event: MouseEvent) {
    if (!this.startTime || !this.startPoint) {
      return;
    }
    const point = new Point(event.offsetX, event.offsetY);
    const duration = Date.now() - this.startTime;
    // Treat quick gestures (less than 100ms) as clicks, and slow gestures
    // (100ms or more) as swipes.
    if (duration < MAX_CLICK_MILLIS) {
      this.action.emit(new ClickAction(point));
    } else {
      this.action.emit(new SwipeAction(this.startPoint, point, duration));
    }
    this.clearGesture();
  }

  /** Resets the current gesture. */
  clearGesture() {
    this.startTime = undefined;
    this.startPoint = undefined;
  }
}
