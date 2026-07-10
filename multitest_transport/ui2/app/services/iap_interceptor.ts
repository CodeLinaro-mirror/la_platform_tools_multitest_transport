/**
 * @fileoverview Intercepts HTTP requests to handle IAP session expiration.
 */

import {
  HttpErrorResponse,
  HttpEvent,
  HttpHandler,
  HttpInterceptor,
  HttpRequest,
} from '@angular/common/http';
import {Injectable} from '@angular/core';
import {EMPTY, Observable, throwError} from 'rxjs';
import {catchError} from 'rxjs/operators';

import {Notifier} from './notifier';

/**
 * Intercepts HTTP requests and checks for IAP session expiration errors.
 * If detected, it displays a clear dialog and suppresses the error to prevent
 * cascading error popups in components.
 */
@Injectable()
export class IapInterceptor implements HttpInterceptor {
  private dialogOpened = false;

  constructor(private readonly notifier: Notifier) {}

  intercept(
    req: HttpRequest<{}>,
    next: HttpHandler,
  ): Observable<HttpEvent<{}>> {
    let modifiedReq = req;
    // Add X-Requested-With header to API calls to force IAP to return 401
    // instead of a 302 redirect (which causes CORS/status 0 errors in XHR).
    if (req.url.includes('/_ah/api/')) {
      modifiedReq = req.clone({
        setHeaders: {
          'X-Requested-With': 'XMLHttpRequest',
        },
      });
    }

    return next.handle(modifiedReq).pipe(
      catchError((error: HttpErrorResponse) => {
        // Only protect API calls, as for Page Load, a Navigation Request,
        // or a Full Page Refresh the GCP will redirect to login page
        // automatically.
        if (req.url.includes('/_ah/api/')) {
          // With X-Requested-With header, IAP should return 401.
          if (error.status === 401) {
            if (!this.dialogOpened) {
              this.dialogOpened = true;
              this.notifier
                .showError(
                  'Your session has expired. Please sign in again and then retry on this page.',
                  undefined,
                  'Session Expired',
                )
                .subscribe(() => {
                  this.dialogOpened = false;
                });
            }
            // Return EMPTY to suppress the error from reaching the component
            return EMPTY;
          }
        }
        // keep the original error for errors that we don't handle there
        // by returning throwError, the error will be caught by the catchError
        // in the service.
        return throwError(() => error);
      }),
    );
  }
}
