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

import {ComponentPortal} from '@angular/cdk/portal';
import {Component} from '@angular/core';

import {HeaderSlotService} from './header_slot_service';

@Component({template: '', standalone: false})
class DummyContent {
}

describe('HeaderSlotService', () => {
  let service: HeaderSlotService;

  beforeEach(() => {
    service = new HeaderSlotService();
  });

  it('is unavailable until the app header registers its slot element', () => {
    expect(service.isAvailable()).toBeFalse();
    expect(service.slotElement$.value).toBeNull();

    const slot = document.createElement('div');
    service.setSlotElement(slot);
    expect(service.isAvailable()).toBeTrue();
    expect(service.slotElement$.value).toBe(slot);

    service.setSlotElement(null);
    expect(service.isAvailable()).toBeFalse();
  });

  it('attaches and detaches content', () => {
    const portal = new ComponentPortal(DummyContent);
    expect(service.portal$.value).toBeNull();

    service.attach(portal);
    expect(service.portal$.value).toBe(portal);

    service.detach(portal);
    expect(service.portal$.value).toBeNull();
  });

  it('only detaches the content that is currently attached', () => {
    const previous = new ComponentPortal(DummyContent);
    const current = new ComponentPortal(DummyContent);
    service.attach(previous);
    service.attach(current);

    // A page being destroyed must not remove the content of the next page.
    service.detach(previous);
    expect(service.portal$.value).toBe(current);

    // Without an argument the slot is always cleared.
    service.detach();
    expect(service.portal$.value).toBeNull();
  });
});
