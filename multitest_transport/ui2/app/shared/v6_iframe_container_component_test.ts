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
import {CommonParamsService} from '../services/common_params_service';
import {
  NavigationEventService,
  NavigationTarget,
} from '../services/navigation_event_service';
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
  // Common query params (e.g. debug, fake_data) captured at SPA bootstrap.
  let commonParams: Record<string, string>;

  beforeEach(async () => {
    commonParams = {};
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
        {
          provide: APP_DATA,
          useValue: {enableLabConsoleUI: true, enableLabConsoleSearchPage: true},
        },
        {
          provide: CommonParamsService,
          useValue: {getCommonParams: () => commonParams},
        },
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

  it('should call iframeNavigate with is_embedded_mode=true when navigateForEntity is called without id', fakeAsync(() => {
    const iframeNavigateSpy = spyOn(component, 'iframeNavigate');
    component.navigateForEntity(EntityType.HOSTS);
    tick();
    expect(iframeNavigateSpy).toHaveBeenCalledWith(
      '/hosts?is_embedded_mode=true',
    );
  }));

  it('should initialize iframeUrl on search page', () => {
    component.initIframeUrl(EntityType.HOSTS);
    expect(component.iframeUrl).toBeDefined();
    expect(component.iframeUrl?.toString()).toContain('is_embedded_mode=true');
  });

  it('should filter search parameters (f, gb, fleet, q) and unallowed parameters when navigateForEntity is called with id', fakeAsync(() => {
    const mockRoute = TestBed.inject(ActivatedRoute);
    (mockRoute.snapshot as unknown as {queryParams: Record<string, string>}).queryParams = {
      'f': 'filter1',
      'gb': 'group1',
      'fleet': 'ats',
      'q': 'pixel',
      'debug': 'true',
      'other': 'val',
    };
    const iframeNavigateSpy = spyOn(component, 'iframeNavigate');
    component.navigateForEntity(EntityType.HOSTS, 'host2');
    tick();
    expect(iframeNavigateSpy).toHaveBeenCalledWith(
      '/hosts/host2?debug=true&is_embedded_mode=true',
    );
  }));

  it('should retain search parameters (f, gb) and filter unallowed parameters when navigateForEntity is called without id', fakeAsync(() => {
    const mockRoute = TestBed.inject(ActivatedRoute);
    (mockRoute.snapshot as unknown as {queryParams: Record<string, string>}).queryParams = {
      'f': 'filter1',
      'gb': 'group1',
      'fleet': 'ats',
      'q': 'pixel',
      'debug': 'true',
      'other': 'val',
    };
    const iframeNavigateSpy = spyOn(component, 'iframeNavigate');
    component.navigateForEntity(EntityType.HOSTS);
    tick();
    expect(iframeNavigateSpy).toHaveBeenCalledWith(
      '/hosts?f=filter1&gb=group1&debug=true&is_embedded_mode=true',
    );
  }));

  it('should filter search parameters (f, gb) and unallowed parameters when initIframeUrl is called with id', () => {
    const mockRoute = TestBed.inject(ActivatedRoute);
    (mockRoute.snapshot as unknown as {queryParams: Record<string, string>}).queryParams = {
      'f': 'filter1',
      'gb': 'group1',
      'fleet': 'ats',
      'q': 'pixel',
      'debug': 'true',
      'other': 'val',
    };
    component.initIframeUrl(EntityType.HOSTS, 'host1');
    expect(component.iframeUrl).toBeDefined();
    const urlStr = component.iframeUrl?.toString() || '';
    expect(urlStr).toContain('/labui/hosts/host1');
    expect(urlStr).toContain('debug=true');
    expect(urlStr).not.toContain('other=val');
    expect(urlStr).not.toContain('f=');
    expect(urlStr).not.toContain('gb=');
    expect(urlStr).not.toContain('fleet=');
    expect(urlStr).not.toContain('q=');
  });

  describe('onMessage', () => {
    it('should handle NAVIGATED message for hosts', () => {
      const event = new MessageEvent('message', {
        data: {
          type: 'NAVIGATED',
          page: MessagePage.HOST_DETAILS,
          params: {host_name: 'host3'},
        },
      });
      Object.defineProperty(event, 'origin', {value: window.location.origin});
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
      Object.defineProperty(event, 'origin', {value: window.location.origin});
      component.onMessage(event);
      expect(router.navigateByUrl).toHaveBeenCalledWith('/devices/device1');
    });

    it('should handle NAVIGATED message with persistent query params', () => {
      commonParams = {'debug': 'true', 'fake_data': '1'};
      const event = new MessageEvent('message', {
        data: {
          type: 'NAVIGATED',
          page: MessagePage.HOST_DETAILS,
          params: {host_name: 'host3'},
        },
      });
      Object.defineProperty(event, 'origin', {value: window.location.origin});
      component.onMessage(event);
      expect(router.navigateByUrl).toHaveBeenCalledWith(
        '/hosts/host3?debug=true&fake_data=1',
      );
    });

    it('should handle SEARCH_STATE_CHANGED message merging persistent query params', () => {
      const navigateSpy = spyOn(router, 'navigate');
      commonParams = {'debug': 'true', 'fake_data': '1'};
      const event = new MessageEvent('message', {
        data: {
          type: 'SEARCH_STATE_CHANGED',
          params: {q: 'pixel'},
        },
      });
      Object.defineProperty(event, 'origin', {value: window.location.origin});
      component.onMessage(event);
      expect(navigateSpy).toHaveBeenCalledWith([], {
        relativeTo: (component as unknown as {route: ActivatedRoute}).route,
        queryParams: {
          'debug': 'true',
          'fake_data': '1',
          'q': 'pixel',
        },
      });
    });

    it('should handle GET_EXTERNAL_URL message with persistent query params', () => {
      commonParams = {'debug': 'true', 'fake_data': '1'};
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
          url: jasmine.stringMatching(/\/hosts\/host4\?debug=true&fake_data=1$/),
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

  it('should do nothing in iframeNavigate if iframe is not present', () => {
    component.iframe = undefined as unknown as ElementRef<HTMLIFrameElement>;
    expect(() => {
      component.iframeNavigate('/some/path');
    }).not.toThrow();
  });

  describe('navMenuClick$', () => {
    it('should navigate to devices url removing search params and unallowed params when DEVICES clicked on search page', () => {
      spyOnProperty(router, 'url', 'get').and.returnValue('/devices?f=filter1&q=pixel&debug=true&lab=atl');
      const iframeNavigateSpy = spyOn(component, 'iframeNavigate');
      const navService = TestBed.inject(NavigationEventService);

      navService.notifyNavMenuClicked(NavigationTarget.DEVICES);

      expect(iframeNavigateSpy).toHaveBeenCalledWith(
        '/devices?debug=true&is_embedded_mode=true',
      );
    });

    it('should navigate to hosts url removing search params and unallowed params when HOSTS clicked on search page', () => {
      spyOnProperty(router, 'url', 'get').and.returnValue('/hosts?f=filter1&gb=group1&fleet=ats&q=pixel&debug=true&lab=atl');
      const iframeNavigateSpy = spyOn(component, 'iframeNavigate');
      const navService = TestBed.inject(NavigationEventService);

      navService.notifyNavMenuClicked(NavigationTarget.HOSTS);

      expect(iframeNavigateSpy).toHaveBeenCalledWith(
        '/hosts?debug=true&is_embedded_mode=true',
      );
    });

    it('should not navigate when on detail page', () => {
      spyOnProperty(router, 'url', 'get').and.returnValue('/devices/dev1');
      const iframeNavigateSpy = spyOn(component, 'iframeNavigate');
      const navService = TestBed.inject(NavigationEventService);

      navService.notifyNavMenuClicked(NavigationTarget.DEVICES);

      expect(iframeNavigateSpy).not.toHaveBeenCalled();
    });
  });

  describe('persistent query parameters propagation', () => {
    it('should append persistent query params to iframe URL in initIframeUrl', () => {
      commonParams = {'debug': 'true', 'fake_data': '1'};
      component.initIframeUrl(EntityType.HOSTS, 'host1');
      const urlStr = component.iframeUrl?.toString() || '';
      expect(urlStr).toContain('debug=true');
      expect(urlStr).toContain('fake_data=1');
      expect(urlStr).toContain('is_embedded_mode=true');
    });

    it('should append persistent query params in navigateForEntity', fakeAsync(() => {
      commonParams = {'debug': 'true', 'fake_data': '1'};
      const iframeNavigateSpy = spyOn(component, 'iframeNavigate');

      component.navigateForEntity(EntityType.HOSTS, 'host1');
      tick();

      expect(iframeNavigateSpy).toHaveBeenCalledWith(
        '/hosts/host1?debug=true&fake_data=1&is_embedded_mode=true',
      );
    }));

    it('should append persistent query params in navigateForSearchReset', () => {
      commonParams = {'debug': 'true', 'fake_data': '1'};
      spyOnProperty(router, 'url', 'get').and.returnValue('/devices?f=filter1');
      const iframeNavigateSpy = spyOn(component, 'iframeNavigate');
      const navService = TestBed.inject(NavigationEventService);

      navService.notifyNavMenuClicked(NavigationTarget.DEVICES);

      expect(iframeNavigateSpy).toHaveBeenCalledWith(
        '/devices?debug=true&fake_data=1&is_embedded_mode=true',
      );
    });

    it('should not overwrite query params from current route if already present', fakeAsync(() => {
      commonParams = {'debug': 'true'};
      const activatedRoute = TestBed.inject(ActivatedRoute);
      (activatedRoute.snapshot as unknown as {queryParams: Record<string, string>}).queryParams = {
        'debug': '1',
      };
      const iframeNavigateSpy = spyOn(component, 'iframeNavigate');

      component.navigateForEntity(EntityType.HOSTS, 'host1');
      tick();

      expect(iframeNavigateSpy).toHaveBeenCalledWith(
        '/hosts/host1?debug=1&is_embedded_mode=true',
      );
    }));
  });
});
