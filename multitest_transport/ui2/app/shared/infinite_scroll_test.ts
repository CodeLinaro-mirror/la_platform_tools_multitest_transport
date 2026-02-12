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

import {Component, Input, ChangeDetectionStrategy} from '@angular/core';
import {DebugElement} from '@angular/core';
import {ComponentFixture, fakeAsync, TestBed, tick} from '@angular/core/testing';
import {NoopAnimationsModule} from '@angular/platform-browser/animations';

import {getEl} from '../testing/jasmine_util';
import {InfiniteScrollLoadEvent} from './infinite_scroll';
import {SharedModule} from './shared_module';

const DEBOUNCE_TIME_MS = 100;

describe('InfiniteScroll', () => {
  let testComponent: TestComponent;
  let scrollable: HTMLElement;
  let testComponentFixture: ComponentFixture<TestComponent>;
  let el: DebugElement;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [NoopAnimationsModule, SharedModule],
      declarations: [TestComponent],
      });
    testComponentFixture = TestBed.createComponent(TestComponent);
    el = testComponentFixture.debugElement;
    testComponent = testComponentFixture.componentInstance;
    testComponent.contentHeightPx = 4000;
    testComponent.scrollHeightPx = 1000;
    testComponent.scrollThreshold = 80;
    testComponentFixture.detectChanges();

    scrollable = getEl(el, '.container');
  });

  it('initializes a component', () => {
    expect(testComponent).toBeTruthy();
  });

  it('does not initially trigger a content load', () => {
    expect(testComponent.loadCount).toBe(0);
  });

  describe('when disabled', () => {
    beforeEach(() => {
      testComponent.enableInfiniteScroll = false;
    });

    it('does not trigger any content loads', fakeAsync(() => {
         scrollable.scrollTop = 2300;
         scrollable.dispatchEvent(new Event('scroll'));
         tick(DEBOUNCE_TIME_MS);
         testComponentFixture.detectChanges();
         expect(testComponent.loadCount).toBe(1);
       }));
  });

  describe('when the element is scrolled within the threshold', () => {
    it('does not trigger a content load', fakeAsync(() => {
         scrollable.scrollTop = 2000;
         // The scroll event will eventually fire in the test browser, but we
         // can't control *when* it fires, and if left alone, will tend to fire
         // asynchronously, after all of the assertions are done, failing the
         // test. Hack is to manually trigger the event.
         scrollable.dispatchEvent(new Event('scroll'));
         tick(DEBOUNCE_TIME_MS);
         expect(testComponent.loadCount).toBe(0);
       }));
  });

  describe('when the element is scrolled past the threshold', () => {
    beforeEach(fakeAsync(() => {
      // Viewport height = 1000, threshold = 80%, content/scroll height = 4000
      // Therefore scrolling should trigger when the bottom is within 800px of
      // the total height, i.e. 4000 - 800 - 1000 = 2200.
      // We'll also simulate a bunch of interim events for debouncing.
      scrollable.scrollTop = 2100;
      scrollable.dispatchEvent(new Event('scroll'));
      scrollable.scrollTop = 2200;
      scrollable.dispatchEvent(new Event('scroll'));
      scrollable.scrollTop = 2300;
      scrollable.dispatchEvent(new Event('scroll'));
      tick(DEBOUNCE_TIME_MS);
      testComponentFixture.detectChanges();
    }));
    it('triggers a content load', () => {
      expect(testComponent.loadCount).toBe(1);
    });

    describe('and the element is scrolled while loading', () => {
      beforeEach(fakeAsync(() => {
        scrollable.scrollTop = 3000;
        scrollable.dispatchEvent(new Event('scroll'));
        tick(DEBOUNCE_TIME_MS);
        scrollable.scrollTop = 3100;
        scrollable.dispatchEvent(new Event('scroll'));
        tick(DEBOUNCE_TIME_MS);
        scrollable.scrollTop = 3200;
        scrollable.dispatchEvent(new Event('scroll'));
        tick(DEBOUNCE_TIME_MS);
      }));

      it('does not trigger more content loads', () => {
        expect(testComponent.loadCount).toBe(1);
      });
    });
  });
});

@Component({
  changeDetection: ChangeDetectionStrategy.Eager,standalone: false,
  template: `<div mttInfiniteScroll
                  class="container"
                  style="overflow-y: scroll"
                  [enableInfiniteScroll]="enableInfiniteScroll"
                  [scrollDebounceTimeMs]="${DEBOUNCE_TIME_MS}"
                  [scrollThreshold]="scrollThreshold"
                  [style.height.px]="scrollHeightPx"
                  (scrollLoad)="logLoad($event)">
               <div [style.height.px]="contentHeightPx"></div>
             </div>`,
// TODO: Make this AOT compatible. See b/352713444
jit: true,

})
class TestComponent {
  complete: (hasMore: boolean) => void = () => {};
  @Input() contentHeightPx = 0;
  @Input() enableInfiniteScroll = true;
  loadCount = 0;
  @Input() scrollHeightPx = 0;
  @Input() scrollThreshold = 0;

  logLoad(e: InfiniteScrollLoadEvent) {
    this.loadCount++;
    e.completed = new Promise<boolean>((resolve) => {
      this.complete = resolve as (hasMore: boolean) => void;
    });
  }
}
