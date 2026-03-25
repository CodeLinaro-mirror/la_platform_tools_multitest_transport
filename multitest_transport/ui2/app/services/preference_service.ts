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

import {inject, Injectable} from '@angular/core';
import {BehaviorSubject} from 'rxjs';

import {APP_DATA} from './app_data';

const USE_LAB_CONSOLE_UI_KEY = 'useLabConsoleUI';

/** Service for user preferences. */
@Injectable({providedIn: 'root'})
export class PreferenceService {
  readonly useLabConsoleUISubject$: BehaviorSubject<boolean>;

  private readonly appData = inject(APP_DATA, {optional: true});

  constructor() {
    this.useLabConsoleUISubject$ = new BehaviorSubject<boolean>(
      this.getInitialUseLabConsoleUiValue(),
    );

    if (this.appData?.enableLabConsoleUI) {
      this.useLabConsoleUISubject$.subscribe((value) => {
        window.localStorage.setItem(USE_LAB_CONSOLE_UI_KEY, String(value));
      });
    }
  }

  private getInitialUseLabConsoleUiValue(): boolean {
    if (!this.appData?.enableLabConsoleUI) {
      return false;
    }
    return window.localStorage.getItem(USE_LAB_CONSOLE_UI_KEY) !== 'false';
  }
}
