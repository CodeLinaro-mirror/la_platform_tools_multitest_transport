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
import {
  ActivatedRoute,
  Event as RouterEvent,
  NavigationEnd,
  provideRouter,
  Router,
} from '@angular/router';
import {BehaviorSubject, Subject} from 'rxjs';

import {APP_DATA} from '../services/app_data';
import {CommonParamsService} from '../services/common_params_service';
import {
  NavigationEventService,
  NavigationTarget,
} from '../services/navigation_event_service';
import {PreferenceService} from '../services/preference_service';
import {HeaderSlotService} from './header_slot_service';
import {
  EMBEDDED_HEADER_SLOT_MESSAGE,
  EMBEDDED_HEADER_SLOT_REQUEST_MESSAGE,
  EntityType,
  HEADER_SEARCH_MODE_CLASS,
  MessagePage,
  V6IframeContainerComponent,
} from './v6_iframe_container_component';

describe('V6IframeContainerComponent', () => {
  let component: V6IframeContainerComponent;
  let fixture: ComponentFixture<V6IframeContainerComponent>;
  let router: Router;
  let useLabConsoleUISubject$: BehaviorSubject<boolean>;
  let useLabConsoleSearchPageSubject$: BehaviorSubject<boolean>;
  // Common query params (e.g. debug, fake_data) captured at SPA bootstrap.
  let commonParams: Record<string, string>;

  beforeEach(async () => {
    commonParams = {};
    useLabConsoleUISubject$ = new BehaviorSubject<boolean>(true);
    useLabConsoleSearchPageSubject$ = new BehaviorSubject<boolean>(true);
    const mockPreferenceService = {
      useLabConsoleUISubject$,
      useLabConsoleSearchPageSubject$,
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
        window.location.origin,
      );
    });

    it('should log an error for unknown message types from the same origin', () => {
      const errorSpy = spyOn(console, 'error');
      const data = {type: 'BOGUS'};
      const event = new MessageEvent('message', {data});
      Object.defineProperty(event, 'origin', {value: window.location.origin});

      component.onMessage(event);

      expect(errorSpy).toHaveBeenCalledOnceWith(
        'Unknown message type:',
        'BOGUS',
        data,
      );
      expect(router.navigateByUrl).not.toHaveBeenCalled();

      // Messages from other origins are ignored silently.
      errorSpy.calls.reset();
      const foreign = new MessageEvent('message', {data: {type: 'BOGUS'}});
      Object.defineProperty(foreign, 'origin', {value: 'https://evil.example'});
      component.onMessage(foreign);
      expect(errorSpy).not.toHaveBeenCalled();
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

  describe('header slot layout', () => {
    let headerSlotService: HeaderSlotService;
    let slot: HTMLElement;
    let iframeEl: HTMLIFrameElement;

    beforeEach(() => {
      headerSlotService = TestBed.inject(HeaderSlotService);
      slot = document.createElement('div');
      slot.style.cssText =
        'position: fixed; left: 300px; top: 10px; width: 500px; height: 40px;';
      document.body.appendChild(slot);
      iframeEl = document.createElement('iframe');
      document.body.appendChild(iframeEl);
      component.iframe = {nativeElement: iframeEl};
      // This container sits right below a 64px app header.
      spyOn(fixture.nativeElement, 'getBoundingClientRect').and.returnValue({
        left: 100,
        top: 64,
        right: 1100,
        bottom: 664,
        width: 1000,
        height: 600,
      } as DOMRect);
    });

    afterEach(() => {
      slot.remove();
      iframeEl.remove();
      headerSlotService.setSlotElement(null);
    });

    it('clips the iframe to the header slot and the content area on search pages and tells the iframe where the slot is', () => {
      spyOnProperty(component, 'isDetailPage', 'get').and.returnValue(false);
      const postMessage =
        spyOn(iframeEl.contentWindow!, 'postMessage') as jasmine.Spy;
      headerSlotService.setSlotElement(slot);

      component.updateHeaderSlotLayout();

      expect(iframeEl.classList).toContain(HEADER_SEARCH_MODE_CLASS);
      expect(iframeEl.style.left).toBe('100px');
      expect(iframeEl.style.width).toBe('1000px');
      expect(iframeEl.style.height).toBe('664px');
      // Slot: x 300..800 on the page => 200..700 relative to the iframe.
      expect(iframeEl.style.clipPath).toBe(
        'polygon(0px 64px, 200px 64px, 200px 0px, 700px 0px, 700px 64px, ' +
          '1000px 64px, 1000px 664px, 0px 664px)',
      );
      expect(postMessage).toHaveBeenCalledOnceWith(
        jasmine.objectContaining({
          type: EMBEDDED_HEADER_SLOT_MESSAGE,
          left: 200,
          width: 500,
          height: 64,
        }),
        window.location.origin,
      );

      // Unchanged geometry is not re-sent, unless the iframe asks for it.
      component.updateHeaderSlotLayout();
      expect(postMessage).toHaveBeenCalledTimes(1);
      component.onMessage({
        origin: window.location.origin,
        data: {type: EMBEDDED_HEADER_SLOT_REQUEST_MESSAGE},
      } as MessageEvent);
      expect(postMessage).toHaveBeenCalledTimes(2);
    });

    it('lets the iframe fill the container on detail pages', () => {
      const isDetailPage = spyOnProperty(component, 'isDetailPage', 'get');
      isDetailPage.and.returnValue(false);
      headerSlotService.setSlotElement(slot);
      component.updateHeaderSlotLayout();
      expect(iframeEl.classList).toContain(HEADER_SEARCH_MODE_CLASS);

      isDetailPage.and.returnValue(true);
      component.updateHeaderSlotLayout();

      expect(iframeEl.classList).not.toContain(HEADER_SEARCH_MODE_CLASS);
      expect(iframeEl.style.left).toBe('');
      expect(iframeEl.style.clipPath).toBe('');
    });

    it('does not use the header slot when the app header has none', () => {
      spyOnProperty(component, 'isDetailPage', 'get').and.returnValue(false);
      const postMessage =
        spyOn(iframeEl.contentWindow!, 'postMessage') as jasmine.Spy;

      component.updateHeaderSlotLayout();

      expect(iframeEl.classList).not.toContain(HEADER_SEARCH_MODE_CLASS);
      expect(postMessage).not.toHaveBeenCalled();
    });

    it('logs and skips the layout when the Lab Console iframe is not rendered', () => {
      spyOnProperty(component, 'isDetailPage', 'get').and.returnValue(false);
      const log = spyOn(console, 'log');
      component.iframe = undefined;

      component.updateHeaderSlotLayout();

      expect(log).toHaveBeenCalledOnceWith(
        'Lab Console iframe is not rendered, skipping the header slot layout.',
      );
    });

    it('re-lays out the iframe once per animation frame after a navigation or a header slot change', async () => {
      const nextFrame = () =>
        new Promise<void>((resolve) => {
          requestAnimationFrame(() => {
            resolve();
          });
        });
      // Let the frame scheduled by the iframe view child setter run first.
      await nextFrame();
      const update = spyOn(component, 'updateHeaderSlotLayout');

      // Two triggers in the same frame are coalesced into a single update,
      // which runs right before the next paint.
      (router.events as Subject<RouterEvent>).next(
        new NavigationEnd(1, '/devices', '/devices'),
      );
      headerSlotService.setSlotElement(slot);
      expect(update).not.toHaveBeenCalled();
      await nextFrame();
      expect(update).toHaveBeenCalledTimes(1);

      // Once the frame has run, the next trigger schedules a new frame.
      (router.events as Subject<RouterEvent>).next(
        new NavigationEnd(2, '/hosts', '/hosts'),
      );
      await nextFrame();
      expect(update).toHaveBeenCalledTimes(2);
    });
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
