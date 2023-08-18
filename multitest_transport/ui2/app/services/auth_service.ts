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

import {Injectable} from '@angular/core';
import {MatDialog} from '@angular/material/dialog';
import {interval, Observable} from 'rxjs';
import {filter, finalize, first, map} from 'rxjs/operators';

import {AuthDialog} from './auth_dialog';
import {AuthorizationInfo} from './mtt_models';

/** Authorization redirect URI. */
export const REDIRECT_URI = window.location.origin + '/auth_return';

const AUTH_WINDOW_NAME = 'authWindow';
const AUTH_WINDOW_FEATURES = 'width=550,height=420,resizable,scrollbars,status';

/** Manage OAuth2 authorization codes. */
@Injectable({
  providedIn: 'root',
})
export class AuthService {
  constructor(private readonly dialog: MatDialog) {}

  /**
   * Fetches an authorization code using automatic or manual copy-paste flows.
   * @param authInfo: authorization information
   * @return authorization code
   */
  getAuthorizationCode(authInfo: AuthorizationInfo): Observable<string|null> {
    if (authInfo.is_manual) {
      return this.getManualAuthorizationCode(authInfo.url);
    }
    return this.getRedirectAuthorizationCode(authInfo.url);
  }

  // Opens a new authorization window or replaces an existing one.
  private static openAuthorizationWindow(authUrl: string): Window|null {
    return window.open(authUrl, AUTH_WINDOW_NAME, AUTH_WINDOW_FEATURES);
  }

  // Ensures the authorization window is closed.
  private static closeAuthorizationWindow(authWindow: Window|null) {
    if (authWindow) {
      authWindow.close();
    }
  }

  // Checks if the authorization window has returned to the redirect URI.
  private static hasAuthorizationReturned(authWindow: Window): boolean {
    try {
      return authWindow.location.host === window.location.host;
    } catch {
      return false;  // Cross-origin access blocked (not returned).
    }
  }

  // Asks the user to manually copy-paste an authorization code.
  private getManualAuthorizationCode(authUrl: string): Observable<string|null> {
    const authWindow = AuthService.openAuthorizationWindow(authUrl);
    // Waits for the user to provide the authorization code.
    return this.dialog.open(AuthDialog, {width: '400px', disableClose: true})
        .afterClosed()
        .pipe(finalize(() => {
          AuthService.closeAuthorizationWindow(authWindow);
        }));
  }

  // Fetches an authorization code automatically by monitoring the authorization
  // window's query parameters after redirection.
  private getRedirectAuthorizationCode(authUrl: string):
      Observable<string|null> {
    const authWindow = AuthService.openAuthorizationWindow(authUrl);
    // Periodically check if the authorization window has returned to the
    // redirect URI with an authorization code.
    return interval(500)
        .pipe(filter(() => {
          if (!authWindow || authWindow.closed) {
            return true;  // Authorization window unexpectedly closed, abort.
          }
          return AuthService.hasAuthorizationReturned(authWindow);
        }))
        .pipe(first())
        .pipe(finalize(() => {
          AuthService.closeAuthorizationWindow(authWindow);
        }))
        .pipe(map(() => {
          return authWindow &&
              new URLSearchParams(authWindow.location.search).get('code');
        }));
  }
}
