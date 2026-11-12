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

import {DOCUMENT} from '@angular/common';
import {TestBed} from '@angular/core/testing';

import {
  CommonParamsService,
  isCommonQueryParam,
  parseCommonQueryParams,
} from './common_params_service';

describe('CommonParamsService', () => {
  /** Creates the service for a page initially visited with the given search. */
  function createService(search: string): CommonParamsService {
    TestBed.configureTestingModule({
      providers: [
        {provide: DOCUMENT, useValue: {defaultView: {location: {search}}}},
      ],
    });
    return TestBed.inject(CommonParamsService);
  }

  it('should capture debug and fake_data from the initial URL', () => {
    const service = createService('?debug=true&fake_data=1&f=filter1&q=pixel');
    expect(service.getCommonParams()).toEqual({
      'debug': 'true',
      'fake_data': '1',
    });
  });

  it('should return an empty record when no common param is active', () => {
    const service = createService('?debug=false&fake_data=0&f=filter1');
    expect(service.getCommonParams()).toEqual({});
  });

  it('should capture the LabConsole force ready flags from the initial URL', () => {
    const service = createService(
      '?force_host_ready=true&force_device_ready=1&force_all_ready=true&force_bulk_config_ready=1&f=filter1',
    );
    expect(service.getCommonParams()).toEqual({
      'force_host_ready': 'true',
      'force_device_ready': '1',
      'force_all_ready': 'true',
      'force_bulk_config_ready': '1',
    });
  });

  it('should return the same immutable record on every call', () => {
    const service = createService('?debug=true');
    expect(Object.isFrozen(service.getCommonParams())).toBeTrue();
    expect(service.getCommonParams()).toBe(service.getCommonParams());
  });

  it('should return an empty record when the document has no window', () => {
    TestBed.configureTestingModule({
      providers: [{provide: DOCUMENT, useValue: {defaultView: null}}],
    });
    expect(TestBed.inject(CommonParamsService).getCommonParams()).toEqual({});
  });

  describe('parseCommonQueryParams', () => {
    it('should capture debug and fake_data when set to true or 1', () => {
      const res = parseCommonQueryParams('?debug=true&fake_data=1&other=test');
      expect(res).toEqual({'debug': 'true', 'fake_data': '1'});
    });

    it('should ignore params when value is not true or 1', () => {
      const res = parseCommonQueryParams('?debug=false&fake_data=0');
      expect(res).toEqual({});
    });

    it('should ignore force ready flags when value is not true or 1', () => {
      const res = parseCommonQueryParams(
        '?force_host_ready=start,restart&force_device_ready=0&force_all_ready=false&force_bulk_config_ready=',
      );
      expect(res).toEqual({});
    });

    it('should ignore params with other values', () => {
      const res = parseCommonQueryParams('?debug=foo&fake_data=bar');
      expect(res).toEqual({});
    });

    it('should handle empty search string', () => {
      expect(parseCommonQueryParams('')).toEqual({});
      expect(parseCommonQueryParams('?')).toEqual({});
    });
  });

  describe('isCommonQueryParam', () => {
    it('should accept common query params only', () => {
      expect(isCommonQueryParam('debug')).toBeTrue();
      expect(isCommonQueryParam('fake_data')).toBeTrue();
      expect(isCommonQueryParam('force_host_ready')).toBeTrue();
      expect(isCommonQueryParam('force_device_ready')).toBeTrue();
      expect(isCommonQueryParam('force_all_ready')).toBeTrue();
      expect(isCommonQueryParam('force_bulk_config_ready')).toBeTrue();
      expect(isCommonQueryParam('f')).toBeFalse();
      expect(isCommonQueryParam('gb')).toBeFalse();
      expect(isCommonQueryParam('is_embedded_mode')).toBeFalse();
      expect(isCommonQueryParam('other')).toBeFalse();
    });
  });
});
