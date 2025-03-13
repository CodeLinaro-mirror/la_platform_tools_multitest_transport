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

import {HTTP_INTERCEPTORS, HttpClient, provideHttpClient, withInterceptorsFromDi} from '@angular/common/http';
import {HttpTestingController, provideHttpClientTesting} from '@angular/common/http/testing';
import {TestBed} from '@angular/core/testing';

import {AnalyticsContext, AnalyticsInterceptor, AnalyticsService} from './analytics_service';
import {AppData} from './app_data';

// Google Analytics global site tag
declare let gtag: Function;

// Placeholder values
const TRACKING_ID = 'testTrackingId';
const PATH = 'testPath';
const TITLE = 'testTitle';
const CATEGORY = 'testCategory';
const ACTION = 'testAction';
const ERROR = 'testError';
const MILLIS = 1234;

/** Test that the AnalyticsService can send information to Google Analytics. */
describe('AnalyticsService', () => {
  let analytics: AnalyticsService;
  let disabledAnalytics: AnalyticsService;

  beforeEach(() => {
    // tslint:disable-next-line:no-any mock gtag function
    (window as any).gtag = jasmine.createSpy('gtag');
    const data: AppData = {analyticsTrackingId: TRACKING_ID, isGoogle: true};
    analytics = new AnalyticsService(data);
    disabledAnalytics = new AnalyticsService({});  // disabled w/o tracking ID
  });

  afterEach(() => {
    // tslint:disable-next-line:no-any mock gtag function
    (window as any).gtag = null;
  });

  describe('trackLocation', () => {
    it('calls gtag config', () => {
      analytics.trackLocation(PATH, TITLE);
      expect(gtag).toHaveBeenCalledWith('config', TRACKING_ID, {
        is_google: 'True',
        page_path: PATH,
        page_title: TITLE,
        custom_map: {dimension1: 'is_google'}
      });
    });

    it('does nothing without tracking ID', () => {
      disabledAnalytics.trackLocation(PATH, TITLE);
      expect(gtag).not.toHaveBeenCalled();
    });
  });

  describe('trackEvent', () => {
    it('calls gtag custom event', () => {
      analytics.trackEvent(CATEGORY, ACTION);
      expect(gtag).toHaveBeenCalledWith(
          'event', ACTION, {is_google: 'True', event_category: CATEGORY});
    });

    it('does nothing without tracking ID', () => {
      disabledAnalytics.trackEvent(CATEGORY, ACTION);
      expect(gtag).not.toHaveBeenCalled();
    });
  });

  describe('trackError', () => {
    it('calls gtag exception event', () => {
      analytics.trackError(ERROR);
      expect(gtag).toHaveBeenCalledWith(
          'event', 'exception', {is_google: 'True', description: ERROR});
    });

    it('does nothing without tracking ID', () => {
      disabledAnalytics.trackError(ERROR);
      expect(gtag).not.toHaveBeenCalled();
    });
  });

  describe('trackTiming', () => {
    it('calls gtag timing_complete event', () => {
      analytics.trackTiming(CATEGORY, ACTION, MILLIS);
      expect(gtag).toHaveBeenCalledWith('event', 'timing_complete', {
        is_google: 'True',
        event_category: CATEGORY,
        name: ACTION,
        value: MILLIS,
      });
    });

    it('does nothing without tracking ID', () => {
      disabledAnalytics.trackTiming(CATEGORY, ACTION, MILLIS);
      expect(gtag).not.toHaveBeenCalled();
    });
  });
});

/** Test that the AnalyticsInterceptor can handle and record HTTP requests. */
describe('AnalyticsInterceptor', () => {
  let interceptor: AnalyticsInterceptor;
  let analytics: AnalyticsService;
  let http: HttpClient;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    analytics = jasmine.createSpyObj(
        'analytics', ['trackEvent', 'trackError', 'trackTiming']);
    interceptor = new AnalyticsInterceptor(analytics);

    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptorsFromDi()), provideHttpClientTesting(),
        {
          provide: HTTP_INTERCEPTORS,
          useValue: interceptor,
          multi: true,
        }
      ]
    });
    http = TestBed.inject(HttpClient);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  describe('intercept', () => {
    it('does nothing without analytics metadata', () => {
      // HTTP request without analytics metadata
      http.get<string>('url').subscribe(data => {
        expect(data).toEqual('response');
      });

      // mock a successful response
      const req = httpMock.expectOne('url');
      req.flush('response');

      // nothing recorded
      expect(analytics.trackEvent).not.toHaveBeenCalled();
      expect(analytics.trackTiming).not.toHaveBeenCalled();
      expect(analytics.trackError).not.toHaveBeenCalled();
    });

    it('records event and timing', () => {
      // HTTP request with analytics metadata
      const context = AnalyticsContext.create(CATEGORY, ACTION);
      http.get<string>('url', {context}).subscribe(data => {
        expect(data).toEqual('response');
      });

      // mock a successful response
      httpMock.expectOne('url').flush('response');

      // event and timing recorded
      expect(analytics.trackEvent).toHaveBeenCalledWith(CATEGORY, ACTION);
      expect(analytics.trackTiming)
          .toHaveBeenCalledWith(CATEGORY, ACTION, jasmine.any(Number));
      expect(analytics.trackError).not.toHaveBeenCalled();
    });

    it('records error status code', () => {
      // HTTP request with analytics metadata
      const context = AnalyticsContext.create(CATEGORY, ACTION);
      http.get<string>('url', {context})
          .subscribe(
              () => {
                fail('expected error');
              },
              error => {
                expect(error.status).toEqual(404);
              });

      // mock an error response
      httpMock.expectOne('url').flush(
          'error', {status: 404, statusText: 'Not Found'});

      // error status code recorded
      expect(analytics.trackEvent).toHaveBeenCalled();
      expect(analytics.trackTiming).toHaveBeenCalled();
      expect(analytics.trackError)
          .toHaveBeenCalledWith(`${CATEGORY} ${ACTION}: 404`);
    });
  });
});
