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

import {ElementRef} from '@angular/core';
import {
  ComponentFixture,
  fakeAsync,
  TestBed,
  tick,
} from '@angular/core/testing';
import {ActivatedRoute, provideRouter, Router} from '@angular/router';
import {BehaviorSubject} from 'rxjs';

import {APP_DATA} from '../services/app_data';
import {PreferenceService} from '../services/preference_service';
import {
  EntityType,
  MessagePage,
  V6IframeContainerComponent,
} from './v6_iframe_container_component';

describe('V6IframeContainerComponent', () => {
  let component: V6IframeContainerComponent;
  let fixture: ComponentFixture<V6IframeContainerComponent>;
  let router: Router;
  let useLabConsoleUISubject$: BehaviorSubject<boolean>;

  beforeEach(async () => {
    useLabConsoleUISubject$ = new BehaviorSubject<boolean>(true);
    const mockPreferenceService = {
      useLabConsoleUISubject$,
    };
    const mockActivatedRoute = {
      snapshot: {
        root: {
          firstChild: {
            routeConfig: {path: 'hosts/:id'},
            params: {id: 'host1'},
          },
        },
      },
    };

    await TestBed.configureTestingModule({
      imports: [V6IframeContainerComponent],
      providers: [
        provideRouter([]),
        {provide: PreferenceService, useValue: mockPreferenceService},
        {provide: ActivatedRoute, useValue: mockActivatedRoute},
        {provide: APP_DATA, useValue: {enableLabConsoleUI: true}},
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(V6IframeContainerComponent);
    component = fixture.componentInstance;
    router = TestBed.inject(Router);
    spyOn(router, 'navigateByUrl');
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should initialize iframeUrl', () => {
    component.initIframeUrl(EntityType.HOSTS, 'host1');
    expect(component.iframeUrl).toBeDefined();
  });

  it('should clear iframeUrl when LabConsole UI is disabled', () => {
    component.initIframeUrl(EntityType.HOSTS, 'host1');
    expect(component.iframeUrl).toBeDefined();

    useLabConsoleUISubject$.next(false);
    expect(component.iframeUrl).toBeUndefined();
  });

  it('should call iframeNavigate when navigateForEntity is called', fakeAsync(() => {
    const iframeNavigateSpy = spyOn(component, 'iframeNavigate');
    component.navigateForEntity(EntityType.HOSTS, 'host2');
    tick();
    expect(iframeNavigateSpy).toHaveBeenCalledWith(
      '/hosts/host2?is_embedded_mode=true',
    );
  }));

  describe('onMessage', () => {
    it('should handle NAVIGATED message for hosts', () => {
      const event = new MessageEvent('message', {
        data: {
          type: 'NAVIGATED',
          page: MessagePage.HOST_DETAILS,
          params: {host_name: 'host3'},
        },
      });
      component.onMessage(event);
      expect(router.navigateByUrl).toHaveBeenCalledWith('/hosts/host3');
    });

    it('should handle NAVIGATED message for devices', () => {
      const event = new MessageEvent('message', {
        data: {
          type: 'NAVIGATED',
          page: MessagePage.DEVICE_DETAILS,
          params: {device_uuid: 'device1'},
        },
      });
      component.onMessage(event);
      expect(router.navigateByUrl).toHaveBeenCalledWith('/devices/device1');
    });

    it('should handle GET_EXTERNAL_URL message', () => {
      const postMessageSpy = jasmine.createSpy('postMessage');
      const mockSource = {postMessage: postMessageSpy};
      const event = new MessageEvent('message', {
        data: {
          type: 'GET_EXTERNAL_URL',
          requestId: 'req1',
          page: MessagePage.HOST_DETAILS,
          params: {host_name: 'host4'},
        },
      });
      Object.defineProperty(event, 'source', {value: mockSource});
      Object.defineProperty(event, 'origin', {value: window.location.origin});

      component.onMessage(event);

      expect(postMessageSpy).toHaveBeenCalledWith(
        jasmine.objectContaining({
          type: 'GET_EXTERNAL_URL_RESPONSE',
          requestId: 'req1',
          url: jasmine.stringMatching(/\/hosts\/host4$/),
        }),
        jasmine.objectContaining({targetOrigin: window.location.origin}),
      );
    });
  });

  it('should post message to iframe in iframeNavigate', () => {
    const mockContentWindow = jasmine.createSpyObj('contentWindow', [
      'postMessage',
    ]);
    const mockIframe: ElementRef<HTMLIFrameElement> = {
      nativeElement: {
        contentWindow: mockContentWindow,
      } as unknown as HTMLIFrameElement,
    };
    component.iframe = mockIframe;

    component.iframeNavigate('/some/path');

    expect(mockContentWindow.postMessage).toHaveBeenCalledWith(
      {type: 'NAVIGATE', url: '/some/path'},
      window.location.origin,
    );
  });
});
