import {
  HTTP_INTERCEPTORS,
  HttpClient,
  provideHttpClient,
  withInterceptorsFromDi,
} from '@angular/common/http';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import {TestBed} from '@angular/core/testing';
import {of as observableOf, Subject} from 'rxjs';

import {IapInterceptor} from './iap_interceptor';
import {Notifier} from './notifier';

describe('IapInterceptor', () => {
  let http: HttpClient;
  let httpMock: HttpTestingController;
  let notifierSpy: jasmine.SpyObj<Notifier>;

  beforeEach(() => {
    notifierSpy = jasmine.createSpyObj('Notifier', ['showError']);
    notifierSpy.showError.and.returnValue(observableOf(undefined));

    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
        {provide: Notifier, useValue: notifierSpy},
        {provide: HTTP_INTERCEPTORS, useClass: IapInterceptor, multi: true},
      ],
    });
    http = TestBed.inject(HttpClient);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('adds X-Requested-With header to /_ah/api/ requests', () => {
    http.get('/_ah/api/mtt/v1/tests').subscribe();
    const req = httpMock.expectOne('/_ah/api/mtt/v1/tests');
    expect(req.request.headers.get('X-Requested-With')).toBe('XMLHttpRequest');
    req.flush({});
  });

  it('does not add X-Requested-With header to other requests', () => {
    http.get('/some/other/path').subscribe();
    const req = httpMock.expectOne('/some/other/path');
    expect(req.request.headers.has('X-Requested-With')).toBeFalse();
    req.flush({});
  });

  it('handles 401 error for /_ah/api/ requests and swallows it', () => {
    let errorCalled = false;
    http.get('/_ah/api/mtt/v1/tests').subscribe({
      error: () => {
        errorCalled = true;
      },
    });

    const req = httpMock.expectOne('/_ah/api/mtt/v1/tests');
    req.flush('Unauthorized', {status: 401, statusText: 'Unauthorized'});

    expect(notifierSpy.showError).toHaveBeenCalledWith(
      'Your session has expired. Please sign in again and then retry on this page.',
      undefined,
      'Session Expired',
    );
    expect(errorCalled).toBeFalse();
  });

  it('propagates other errors for /_ah/api/ requests', () => {
    let errorCalled = false;
    http.get('/_ah/api/mtt/v1/tests').subscribe({
      error: () => {
        errorCalled = true;
      },
    });

    const req = httpMock.expectOne('/_ah/api/mtt/v1/tests');
    req.flush('Forbidden', {status: 403, statusText: 'Forbidden'});

    expect(notifierSpy.showError).not.toHaveBeenCalled();
    expect(errorCalled).toBeTrue();
  });

  it('only opens one dialog at a time', () => {
    const dialogCloseSubject = new Subject<void>();
    notifierSpy.showError.and.returnValue(dialogCloseSubject);

    // Trigger first 401
    http.get('/_ah/api/a').subscribe();
    const req1 = httpMock.expectOne('/_ah/api/a');
    req1.flush('Unauthorized', {status: 401, statusText: 'Unauthorized'});

    expect(notifierSpy.showError).toHaveBeenCalledTimes(1);

    // Trigger second 401 while dialog is still "open"
    http.get('/_ah/api/b').subscribe();
    const req2 = httpMock.expectOne('/_ah/api/b');
    req2.flush('Unauthorized', {status: 401, statusText: 'Unauthorized'});

    expect(notifierSpy.showError).toHaveBeenCalledTimes(1); // Still 1!

    // Close dialog
    dialogCloseSubject.next();
    dialogCloseSubject.complete();

    // Trigger third 401
    http.get('/_ah/api/c').subscribe();
    const req3 = httpMock.expectOne('/_ah/api/c');
    req3.flush('Unauthorized', {status: 401, statusText: 'Unauthorized'});

    expect(notifierSpy.showError).toHaveBeenCalledTimes(2); // Bumped to 2!
  });
});
