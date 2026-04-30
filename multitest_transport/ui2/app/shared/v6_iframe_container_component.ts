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

import {CommonModule} from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  HostListener,
  inject,
  OnDestroy,
  OnInit,
  ViewChild,
} from '@angular/core';
import {SafeResourceUrl} from '@angular/platform-browser';
import {ActivatedRoute, Router, RouterModule} from '@angular/router';
import {ReplaySubject} from 'rxjs';
import {takeUntil} from 'rxjs/operators';
import {appendParams, TrustedResourceUrl, trustedResourceUrl} from 'safevalues';

import {APP_DATA} from '../services/app_data';
import {PreferenceService} from '../services/preference_service';

/**
 * Entity types supported by the V6 iframe container.
 */
export enum EntityType {
  HOSTS = 'hosts',
  DEVICES = 'devices',
}

/**
 * Message pages supported by the V6 iframe container.
 */
export enum MessagePage {
  HOST_DETAILS = 'host_details',
  DEVICE_DETAILS = 'device_details',
}

/**
 * Shared container for V6 iframe pages in UI2.
 * This component persists across Host and Device detail pages,
 * allowing the iframe to remain alive during client-side navigation.
 */
@Component({
  changeDetection: ChangeDetectionStrategy.Eager,
  standalone: true,
  imports: [CommonModule, RouterModule],
  selector: 'v6-iframe-container',
  templateUrl: './v6_iframe_container_component.ng.html',
  styles: [
    `
    :host {
      display: flex;
      flex-direction: column;
      height: 100%;
    }
  `,
  ],
})
export class V6IframeContainerComponent implements OnInit, OnDestroy {
  protected readonly route = inject(ActivatedRoute);
  protected readonly router = inject(Router);
  readonly appData = inject(APP_DATA);
  readonly preferenceService = inject(PreferenceService);

  @ViewChild('iframe') iframe?: ElementRef<HTMLIFrameElement>;

  iframeNavigate(url: string) {
    if (this.iframe && this.iframe.nativeElement.contentWindow) {
      const parsedUrl = new URL(url, window.location.origin);
      this.iframe.nativeElement.contentWindow.postMessage(
        {type: 'NAVIGATE', url: parsedUrl.pathname + parsedUrl.search},
        window.location.origin,
      );
    }
  }

  navigateForEntity(type: EntityType, id: string) {
    if (this.appData?.enableLabConsoleUI) {
      Promise.resolve().then(() => {
        const url = `/${type}/${id}?is_embedded_mode=true`;
        this.iframeNavigate(url);
      });
    }
  }

  private readonly destroy = new ReplaySubject<void>();

  iframeUrl?: SafeResourceUrl;

  ngOnInit() {
    this.preferenceService.useLabConsoleUISubject$
      .pipe(takeUntil(this.destroy))
      .subscribe((useLabConsoleUI) => {
        if (!useLabConsoleUI) {
          // Clear the iframe URL when LabConsole UI is disabled.
          // So that iframeUrl could be set when user re-enables LabConsole UI.
          this.iframeUrl = undefined;
        }
      });
  }

  ngOnDestroy() {
    this.destroy.next();
    this.destroy.complete();
  }

  initIframeUrl(type: EntityType, id: string) {
    if (!this.iframeUrl) {
      let baseUrl: TrustedResourceUrl;
      if (type === EntityType.HOSTS) {
        baseUrl = trustedResourceUrl`/labui/hosts/${id}`;
      } else if (type === EntityType.DEVICES) {
        baseUrl = trustedResourceUrl`/labui/devices/${id}`;
      } else {
        throw new Error(`Unsupported entity type: ${type}`);
      }

      this.iframeUrl = appendParams(baseUrl, {'is_embedded_mode': ['true']});
    }
  }

  @HostListener('window:message', ['$event'])
  onMessage(event: MessageEvent) {
    const data = event.data;
    if (!data) return;

    if (data.type === 'GET_EXTERNAL_URL') {
      const {requestId, page, params} = data;
      let url = '';
      if (page === MessagePage.HOST_DETAILS) {
        url = `/hosts/${params['host_name']}`;
      } else if (page === MessagePage.DEVICE_DETAILS) {
        url = `/devices/${params['device_uuid'] || params['uuid']}`;
      } else {
        throw new Error(`Unsupported page type in GET_EXTERNAL_URL: ${page}`);
      }

      const absoluteUrl = `${window.location.origin}${url}`;
      (event.source as Window).postMessage(
        {
          type: 'GET_EXTERNAL_URL_RESPONSE',
          requestId,
          url: absoluteUrl,
        },
        {targetOrigin: event.origin},
      );
    } else if (data.type === 'NAVIGATED') {
      const {page, params} = data;
      let url = '';
      if (page === MessagePage.HOST_DETAILS) {
        url = `/hosts/${params['host_name']}`;
      } else if (page === MessagePage.DEVICE_DETAILS) {
        url = `/devices/${params['device_uuid'] || params['uuid']}`;
      } else {
        throw new Error(`Unsupported page type in NAVIGATED: ${page}`);
      }

      this.router.navigateByUrl(url);
    }
  }
}
