/**
 * Copyright 2020 Google LLC
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

import {LiveAnnouncer} from '@angular/cdk/a11y';
import {Location} from '@angular/common';
import {AfterViewChecked, ChangeDetectorRef, Component, ElementRef, inject, Input, OnChanges, OnDestroy, OnInit, SimpleChanges, ViewChild} from '@angular/core';
import {MAT_DIALOG_DATA} from '@angular/material/dialog';
import {MatTabChangeEvent} from '@angular/material/tabs';
import {Router} from '@angular/router';
import {ReplaySubject} from 'rxjs';
import {filter, finalize, switchMap, takeUntil} from 'rxjs/operators';
import {trustedResourceUrl} from 'safevalues';
import {IframeIntent, setIframeSrcWithIntent} from 'safevalues/dom';

import {APP_DATA} from '../services/app_data';
import {FeedbackService} from '../services/feedback_service';
import {LabHostInfo, NoteType, SurveyTrigger} from '../services/mtt_lab_models';
import {Notifier} from '../services/notifier';
import {PreferenceService} from '../services/preference_service';
import {StorageService} from '../services/storage_service';
import {TfcClient} from '../services/tfc_client';
import {TestHarness} from '../services/tfc_models';
import {UserService} from '../services/user_service';
import {assertRequiredInput} from '../shared/util';

import {HostDetailsSummary} from './host_details_summary';

/**
 * Data format when passed to HostDetails.
 */
export interface HostDetailsDialogParams {
  id: string;
  newWindow: boolean;
}

/**
 * Displays host details information.
 */
@Component({
  standalone: false,
  selector: 'host-details',
  styleUrls: ['host_details.css'],
  templateUrl: './host_details.ng.html',
})
export class HostDetails implements AfterViewChecked, OnChanges, OnDestroy,
                                    OnInit {
  @Input() id = '';
  @ViewChild(HostDetailsSummary, {static: true})
  hostDetailsSummary!: HostDetailsSummary;
  @ViewChild('iframe') iframe?: ElementRef;
  newWindow = false;
  readonly noteType = NoteType.HOST;
  isLoading = false;
  previousRoute = '';
  readonly defaultBackRoute = 'hosts';
  readonly testHarness = TestHarness;
  private readonly destroy = new ReplaySubject<void>();
  data?: LabHostInfo;
  isModalMode = false;
  hostnames: string[] = [];
  hostnamesStorageKey = '';

  private readonly cdRef = inject(ChangeDetectorRef);
  private readonly feedbackService = inject(FeedbackService);
  private readonly liveAnnouncer = inject(LiveAnnouncer);
  private readonly location = inject(Location);
  private readonly notifier = inject(Notifier);
  private readonly router = inject(Router);
  private readonly storageService = inject(StorageService);
  private readonly tfcClient = inject(TfcClient);
  readonly userService = inject(UserService);
  readonly appData = inject(APP_DATA);
  readonly preferenceService = inject(PreferenceService);
  readonly params: HostDetailsDialogParams|null =
      inject(MAT_DIALOG_DATA, {optional: true});

  ngOnChanges(changes: SimpleChanges) {
    if (changes['id'] && !changes['id'].firstChange) {
      this.load(changes['id'].currentValue);
      this.appendDefaultOption();
      // Load the iframe after the id to display changed
      this.loadIframe();
    }
  }

  ngOnInit() {
    if (this.params && this.params.id) {
      this.isModalMode = true;
      this.id = this.params.id;
      this.newWindow = this.params.newWindow;
    }
    this.hostnames = this.storageService.hostList;

    assertRequiredInput(this.id, 'id', 'hostDetails');
    assertRequiredInput(
        this.hostDetailsSummary, 'hostDetailsSummary', 'hostDetails');
    this.load(this.id);
    this.appendDefaultOption();
    if (this.appData?.enableLabConsoleUI) {
      this.preferenceService.useLabConsoleUISubject$
          .pipe(takeUntil(this.destroy))
          .subscribe((useLabConsoleUI) => {
            if (useLabConsoleUI) {
              setTimeout(() => {
                this.loadIframe();
              }, 0);
            }
          });
    }
  }

  ngOnDestroy() {
    this.destroy.next();
    this.destroy.complete();
  }

  ngAfterViewChecked() {
    this.cdRef.detectChanges();
  }

  loadIframe() {
    if (this.iframe && this.id) {
      const url =
          trustedResourceUrl`/newUI/hosts/${this.id}?is_embedded_mode=true`;
      setIframeSrcWithIntent(
          this.iframe.nativeElement,
          IframeIntent.EMBEDDED_INTERNAL_CONTENT,
          url,
      );
    }
  }

  appendDefaultOption() {
    if (this.id && !this.hostnames.includes(this.id)) {
      this.hostnames.push(this.id);
    }
  }

  load(hostname: string, switchParam = false) {
    this.isLoading = true;
    if (switchParam) {
      this.updateUrlByHostname(hostname);
    }
    this.tfcClient.getHostInfo(this.id)
        .pipe(
            takeUntil(this.destroy),
            finalize(() => {
              this.isLoading = false;
            }),
            )
        .subscribe(
            (result) => {
              this.data = result;
              this.liveAnnouncer.announce('Host info loaded', 'assertive');
            },
            () => {
              this.notifier.showError(`Failed to load host ${this.id}`);
            },
        );
  }

  back() {
    this.location.back();
  }

  /**
   * Refreshes the host data. Called after users mark the host as fixed or
   * verified.
   */
  refresh() {
    this.load(this.id);
    this.hostDetailsSummary.loadHost(this.id);
  }

  /** When host state is GONE, user can remove(hide) the host. */
  removeHost() {
    this.notifier.confirm('', 'Remove host?', 'Remove host', 'Cancel')
        .pipe(
            filter(
                isConfirmed =>
                    isConfirmed !== false),  // Remove canceled confirmation.
            switchMap((result) => {
              this.isLoading = true;
              return this.tfcClient.removeHost(this.id);
            }),
            takeUntil(this.destroy),
            finalize(() => {
              this.isLoading = false;
            }),
            )
        .subscribe(
            () => {
              if (this.data) {
                this.data.hidden = true;
              }
              this.notifier.showMessage(`Host '${this.id}' removed`);
            },
            () => {
              this.notifier.showError(`Failed to remove host ${this.id}`);
            });
  }

  startHostNotesHats(event: MatTabChangeEvent) {
    if (event.tab.textLabel === 'Notes') {
      this.feedbackService.startSurvey(SurveyTrigger.HOST_NOTES);
    }
  }

  startHostNavigationHats() {
    this.feedbackService.startSurvey(SurveyTrigger.HOST_NAVIGATION);
  }

  /** Updates current URL string. */
  updateUrlByHostname(hostname: string) {
    const url = this.router.serializeUrl(
        this.router.createUrlTree(['/hosts', hostname]));
    this.router.navigate([url], {replaceUrl: true});
  }
}
