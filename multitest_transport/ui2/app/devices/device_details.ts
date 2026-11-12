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
import {TemplatePortal} from '@angular/cdk/portal';
import {Component, ElementRef, inject, Input, OnChanges, OnDestroy, OnInit, SimpleChanges, TemplateRef, ViewChild, ViewContainerRef, ChangeDetectionStrategy} from '@angular/core';
import {MAT_DIALOG_DATA} from '@angular/material/dialog';
import {MatTabChangeEvent} from '@angular/material/tabs';
import {Router} from '@angular/router';
import {ReplaySubject} from 'rxjs';
import {takeUntil} from 'rxjs/operators';
import {EntityType, V6IframeContainerComponent} from '../shared/v6_iframe_container_component';

import {APP_DATA, AppData} from '../services/app_data';
import {CommonParamsService} from '../services/common_params_service';
import {FeedbackService} from '../services/feedback_service';
import {LabDeviceInfo, NoteType, SurveyTrigger} from '../services/mtt_lab_models';
import {Notifier} from '../services/notifier';
import {PreferenceService} from '../services/preference_service';
import {DeviceSerialWithDisplay, StorageService} from '../services/storage_service';
import {TfcClient} from '../services/tfc_client';
import {HeaderSlotService} from '../shared/header_slot_service';
import {buildApiErrorMessage} from '../shared/util';

/**
 * Data format when passed to DeviceDetails.
 */
export interface DeviceDetailsDialogParams {
  id: string;
  newWindow: boolean;
}

/**
 * A component for displaying device details information.
 */
@Component({
  changeDetection: ChangeDetectionStrategy.Eager,standalone: false,
  selector: 'device-details',
  styleUrls: ['device_details.css'],
  templateUrl: './device_details.ng.html',
})
export class DeviceDetails implements OnChanges, OnDestroy, OnInit {
  @ViewChild('iframe') iframe?: ElementRef;
  @Input() id = '';
  @Input() newWindow = false;
  readonly noteType = NoteType.DEVICE;
  previousRoute = '';
  previousId = '';
  readonly defaultBackRoute = 'devices';
  isLoading = false;
  private readonly destroy = new ReplaySubject<void>();
  isModalMode = false;
  deviceSerialsWithDisplay: DeviceSerialWithDisplay[] = [];
  data?: LabDeviceInfo;
  /**
   * Whether the page header (back button, breadcrumb, device switcher) is
   * rendered in the app header slot instead of the page's own sub-header.
   */
  isHeaderInAppHeaderSlot = false;
  @ViewChild('headerSlotContent', {static: true})
  headerSlotContent!: TemplateRef<unknown>;
  private headerPortal?: TemplatePortal;

  private readonly commonParamsService = inject(CommonParamsService);
  private readonly feedbackService = inject(FeedbackService);
  private readonly headerSlotService = inject(HeaderSlotService);
  private readonly liveAnnouncer = inject(LiveAnnouncer);
  private readonly notifier = inject(Notifier);
  private readonly router = inject(Router);
  private readonly storageService = inject(StorageService);
  private readonly tfcClient = inject(TfcClient);
  private readonly viewContainerRef = inject(ViewContainerRef);
  readonly params: DeviceDetailsDialogParams|null =
      inject(MAT_DIALOG_DATA, {optional: true});
  readonly appData: AppData|null = inject(APP_DATA, {optional: true});
  preferenceService: PreferenceService|null =
      inject(PreferenceService, {optional: true});
  readonly container = inject(V6IframeContainerComponent, {optional: true});

  ngOnChanges(changes: SimpleChanges) {
    if (changes['id'] && !changes['id'].firstChange) {
      this.load(changes['id'].currentValue);
      this.appendDefaultOption();
      // when the id changed(e.g. the user switches between devices via the
      // device list in the header), we need to update the iframe URL.
      if (this.container) {
        this.container.navigateForEntity(EntityType.DEVICES, this.id);
      }
    }
  }

  ngOnInit() {
    if (this.params && this.params.id) {
      this.isModalMode = true;
      this.id = this.params.id;
      this.newWindow = this.params.newWindow;
    }
    this.deviceSerialsWithDisplay = this.storageService.deviceList;
    this.load(this.id);
    this.appendDefaultOption();
    if (this.appData?.enableLabConsoleUI) {
      this.preferenceService!.useLabConsoleUISubject$
          .pipe(takeUntil(this.destroy))
          .subscribe((useLabConsoleUI) => {
            this.syncHeaderSlot(useLabConsoleUI);
            if (useLabConsoleUI && this.container) {
              this.container.initIframeUrl(EntityType.DEVICES, this.id);
            }
          });
    }
  }

  ngOnDestroy() {
    if (this.headerPortal) {
      this.headerSlotService.detach(this.headerPortal);
    }
    this.destroy.next();
    this.destroy.complete();
  }

  /**
   * Moves the page header into the app header slot while the Lab Console UI
   * renders this page, and back into the page otherwise.
   *
   * @param useLabConsoleUI Whether the Lab Console UI is active.
   *
   * Explanation:
   * In Lab Console mode the page content is the embedded V6 iframe, so the
   * back button, the "Devices" breadcrumb and the device switcher are shown in
   * the app header (HeaderSlotService) and the page's own sub-header is not
   * rendered, giving the iframe the full height. The dialog (modal) variant and
   * pages without an app header keep the sub-header.
   */
  private syncHeaderSlot(useLabConsoleUI: boolean) {
    const inSlot = useLabConsoleUI && !this.isModalMode &&
        this.headerSlotService.isAvailable();
    if (inSlot === this.isHeaderInAppHeaderSlot) {
      return;
    }
    this.isHeaderInAppHeaderSlot = inSlot;
    if (inSlot) {
      this.headerPortal = this.headerPortal ??
          new TemplatePortal(this.headerSlotContent, this.viewContainerRef);
      // Attaching from ngOnInit, i.e. in the middle of a change detection
      // pass that has already checked the app header, is fine: the outlet's
      // async pipe marks the app component for check and Angular refreshes it
      // again in the same tick (no NG0100, no extra frame).
      this.headerSlotService.attach(this.headerPortal);
    } else if (this.headerPortal) {
      this.headerSlotService.detach(this.headerPortal);
    }
  }

  get deviceSerials() {
    return this.deviceSerialsWithDisplay.map(
        deviceSerialWithDisplay => deviceSerialWithDisplay.serial);
  }

  load(deviceSerial: string, switchParam = false) {
    this.isLoading = true;
    if (switchParam) {
      this.updateUrlByDeviceSerial(deviceSerial);
    }
    this.liveAnnouncer.announce('Loading', 'polite');
    this.tfcClient.getDeviceInfo(deviceSerial)
        .pipe(
            takeUntil(this.destroy),
            )
        .subscribe(
            (result) => {
              this.data = result;
              this.liveAnnouncer.announce('Device info loaded', 'assertive');
            },
            (error) => {
              this.notifier.showError(
                  `Failed to get device with id ${deviceSerial}.`,
                  buildApiErrorMessage(error));
            },
        );
  }

  closeLoading() {
    // To prevent ExpressionChangedAfterItHasBeenCheckedError: Expression has
    // changed after it was checked.
    setTimeout(() => {
      this.isLoading = false;
    }, 0);
  }

  back() {
    window.history.back();
  }

  appendDefaultOption() {
    if (this.id && !this.deviceSerials.includes(this.id)) {
      this.deviceSerialsWithDisplay.push({
        serial: this.id,
        serialForDisplay: this.id,
      });
    }
  }

  startDeviceHistoryHats(event: MatTabChangeEvent) {
    if (event.tab.textLabel === 'History') {
      this.feedbackService.startSurvey(SurveyTrigger.DEVICE_HISTORY);
    }
  }

  startDeviceNavigationHats() {
    this.feedbackService.startSurvey(SurveyTrigger.DEVICE_NAVIGATION);
  }

  /**
   * Updates current URL string, preserving the common query parameters (e.g.
   * debug, fake_data) captured at SPA bootstrap.
   */
  updateUrlByDeviceSerial(deviceSerial: string) {
    const url = this.router.serializeUrl(
        this.router.createUrlTree(['/devices', deviceSerial]));
    this.router.navigate([url], {
      queryParams: this.commonParamsService.getCommonParams(),
      replaceUrl: true,
    });
  }
}
