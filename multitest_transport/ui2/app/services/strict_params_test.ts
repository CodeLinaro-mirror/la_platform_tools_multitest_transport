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

import {HTTP_INTERCEPTORS, HttpClient, HttpParams, provideHttpClient, withInterceptorsFromDi} from '@angular/common/http';
import {HttpTestingController, provideHttpClientTesting} from '@angular/common/http/testing';
import {TestBed} from '@angular/core/testing';

import {StrictParamsInterceptor} from './strict_params';

/** Test that the StrictParamsInterceptor can encode parameters. */
describe('StrictParameterInterceptor', () => {
  let interceptor: StrictParamsInterceptor;
  let http: HttpClient;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    interceptor = new StrictParamsInterceptor();

    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptorsFromDi()), provideHttpClientTesting(),
        {provide: HTTP_INTERCEPTORS, useValue: interceptor, multi: true}
      ]
    });
    // Keeping it compatible with Angular 8,
    // tslint:disable-next-line:deprecation
    http = TestBed.get(HttpClient);
    // tslint:disable-next-line:deprecation
    httpMock = TestBed.get(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('can encode key', () => {
    const params = new HttpParams().set('_@_:_$_,_;_+_=_?_/_', 'value');
    http.get('url', {params}).subscribe();
    httpMock.expectOne(
        req => req.urlWithParams ===
            'url?_%40_%3A_%24_%2C_%3B_%2B_%3D_%3F_%2F_=value');
  });

  it('can encode value', () => {
    const params = new HttpParams().set('key', '_@_:_$_,_;_+_=_?_/_');
    http.get('url', {params}).subscribe();
    httpMock.expectOne(
        req => req.urlWithParams ===
            'url?key=_%40_%3A_%24_%2C_%3B_%2B_%3D_%3F_%2F_');
  });
});
