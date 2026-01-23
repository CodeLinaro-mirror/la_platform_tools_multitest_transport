
import {inject, Injectable} from '@angular/core';
import {BehaviorSubject} from 'rxjs';

import {APP_DATA, AppData} from './app_data';

const USE_LAB_CONSOLE_UI_KEY = 'useLabConsoleUI';

/** Service for user preferences. */
@Injectable({providedIn: 'root'})
export class PreferenceService {
  readonly useLabConsoleUISubject$: BehaviorSubject<boolean>;

  private readonly appData: AppData = inject(APP_DATA);

  constructor() {
    // true by default if new UI enabled.

    // when feature flag is disabled, no need to read from local storage.
    if (this.appData.enableLabConsoleUI) {
      const useLabConsoleUI =
          window.localStorage.getItem(USE_LAB_CONSOLE_UI_KEY) !== 'false' ?
          true :
          false;
      this.useLabConsoleUISubject$ =
          new BehaviorSubject<boolean>(useLabConsoleUI);
      this.useLabConsoleUISubject$.subscribe((value) => {
        window.localStorage.setItem(USE_LAB_CONSOLE_UI_KEY, String(value));
      });
    } else {
      this.useLabConsoleUISubject$ = new BehaviorSubject<boolean>(false);
    }
  }
}
