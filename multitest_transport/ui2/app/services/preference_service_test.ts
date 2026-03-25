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

import {TestBed} from '@angular/core/testing';
import {APP_DATA} from './app_data';
import {PreferenceService} from './preference_service';

describe('PreferenceService', () => {
  let service: PreferenceService;
  const mockAppData = {
    enableLabConsoleUI: true,
  };

  beforeEach(() => {
    window.localStorage.clear();
    TestBed.configureTestingModule({
      providers: [
        PreferenceService,
        {provide: APP_DATA, useValue: mockAppData},
      ],
    });
  });

  it('should initialize with true by default if feature flag is on', () => {
    service = TestBed.inject(PreferenceService);
    expect(service.useLabConsoleUISubject$.value).toBeTrue();
  });

  it('should initialize with value from local storage', () => {
    window.localStorage.setItem('useLabConsoleUI', 'false');
    service = TestBed.inject(PreferenceService);
    expect(service.useLabConsoleUISubject$.value).toBeFalse();
  });

  it('should update local storage when subject changes', () => {
    service = TestBed.inject(PreferenceService);
    service.useLabConsoleUISubject$.next(false);
    expect(window.localStorage.getItem('useLabConsoleUI')).toBe('false');
  });

  it('should be false if feature flag is off', () => {
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      providers: [
        PreferenceService,
        {provide: APP_DATA, useValue: {enableLabConsoleUI: false}},
      ],
    });
    service = TestBed.inject(PreferenceService);
    expect(service.useLabConsoleUISubject$.value).toBeFalse();
  });
});
