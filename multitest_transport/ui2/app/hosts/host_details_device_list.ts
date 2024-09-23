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
import {Component, ElementRef, HostListener, Input, OnChanges, OnDestroy, OnInit, SimpleChanges, ViewChild} from '@angular/core';
import {Router} from '@angular/router';
import {ReplaySubject} from 'rxjs';
import {finalize, mergeMap, takeUntil} from 'rxjs/operators';

import {DeviceListTable} from '../devices/device_list_table';
import {FeedbackService} from '../services/feedback_service';
import {LabDeviceInfo, SurveyTrigger} from '../services/mtt_lab_models';
import {Notifier} from '../services/notifier';
import {TfcClient} from '../services/tfc_client';
import {NoteList} from '../services/tfc_models';
import {UserService} from '../services/user_service';
import {assertRequiredInput} from '../shared/util';

/** Display a list of devices from a host. */
@Component({
  standalone: false,
  selector: 'host-details-device-list',
  styleUrls: ['host_details_device_list.css'],
  templateUrl: './host_details_device_list.ng.html',
})
export class HostDetailsDeviceList implements OnChanges, OnDestroy, OnInit {
  @ViewChild(DeviceListTable, {static: true}) deviceListTable!: DeviceListTable;

  @Input() id = '';
  @Input() newWindow = false;
  @Input() isModalMode = false;
  @Input() labName = '';

  private readonly destroy = new ReplaySubject<void>();
  deviceInfos: LabDeviceInfo[] = [];
  isLoading = false;
  deviceHostMap: Array < [string, string] >= [];

  get deviceSerials() {
    return this.deviceInfos.map(info => info.device_serial);
  }

  constructor(
      private readonly feedbackService: FeedbackService,
      private readonly liveAnnouncer: LiveAnnouncer,
      private readonly notifier: Notifier,
      private readonly router: Router,
      private readonly tfcClient: TfcClient,
      readonly userService: UserService,
  ) {}

  ngOnChanges(changes: SimpleChanges) {
    if (changes['id'] && !changes['id'].firstChange) this.load(this.id);
  }

  ngOnInit() {
    assertRequiredInput(
        this.deviceListTable, 'deviceListTable', 'HostDetailsDeviceList');
    this.load(this.id);
  }

  ngOnDestroy() {
    this.destroy.next();
  }

  load(hostname: string) {
    this.isLoading = true;
    this.liveAnnouncer.announce('Loading', 'polite');
    this.tfcClient.getDeviceInfosFromHost(hostname)
        .pipe(
            mergeMap((result) => {
              this.deviceInfos = result.deviceInfos || [];
              return this.tfcClient.batchGetDevicesLatestNotes(
                  this.deviceSerials);
            }),
            finalize(() => {
              this.isLoading = false;
            }),
            takeUntil(this.destroy),
            )
        .subscribe(
            (result) => {
              this.deviceHostMap =
                  this.deviceInfos.map(info => [info.device_serial, this.id]);
              this.setDeviceNotes(result);
              this.liveAnnouncer.announce('Device list loaded', 'assertive');
            },
            (error) => {
              this.notifier.showError(
                  `Failed to load device list for host ${hostname}`);
            },
        );
  }

  /** Loads the latest updated notes after the add notes dialog is closed. */
  loadDeviceNotes(deviceSerials: string[]) {
    this.tfcClient.batchGetDevicesLatestNotes(deviceSerials)
        .pipe(takeUntil(this.destroy))
        .subscribe(
            (result) => {
              if (result) {
                this.setDeviceNotes(result);
              }
            },
            (error) => {
              this.notifier.showError(
                  'Failed to load latest notes for devices');
            });
  }

  reloadDevices(deviceSerials: string[]) {
    this.loadDeviceNotes(deviceSerials);
  }

  setDeviceNotes(noteList: NoteList) {
    const newDeviceInfos = [...this.deviceInfos];
    if (noteList && noteList.notes) {
      for (const note of noteList.notes) {
        const deviceInfo = newDeviceInfos.find(
            info => info.device_serial === note.device_serial);
        if (deviceInfo) {
          deviceInfo.note = note;
        }
      }
      this.deviceInfos = newDeviceInfos;
    }
  }

  startChangeSortHats() {
    this.feedbackService.startSurvey(SurveyTrigger.SORT_DEVICE_DATA);
  }

  startViewDevicesColumnsHats() {
    this.feedbackService.startSurvey(SurveyTrigger.VIEW_DEVICES_COLUMNS);
  }

  startBatchAddDevicesNotesHats() {
    this.feedbackService.startSurvey(SurveyTrigger.BATCH_ADD_DEVICES_NOTES);
  }
}
