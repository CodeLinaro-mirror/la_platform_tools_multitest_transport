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
import {Component, ElementRef, EventEmitter, HostListener, Input, OnChanges, OnDestroy, OnInit, Output, SimpleChanges, ViewChild, ChangeDetectionStrategy} from '@angular/core';
import {MatDialog, MatDialogRef} from '@angular/material/dialog';
import {MatTable} from '@angular/material/table';
import {Notifier} from 'google3/third_party/py/multitest_transport/ui2/app/services/notifier';
import {TableRowsSelectManager} from 'google3/third_party/py/multitest_transport/ui2/app/shared/table_rows_select';
import {assertRequiredInput} from 'google3/third_party/py/multitest_transport/ui2/app/shared/util';
import {ReplaySubject} from 'rxjs';
import {finalize, takeUntil} from 'rxjs/operators';

import {DeviceDetails, DeviceDetailsDialogParams} from '../devices/device_details';
import {NoteDialogParams, NoteDialogState, NotesDialog} from '../notes/notes_dialog';
import {LabDeviceInfo, NoteType} from '../services/mtt_lab_models';
import {TfcClient} from '../services/tfc_client';
import {UserService} from '../services/user_service';

/**
 * Display a list of devices from a recovering host.
 * A recovering host is a host which its assignee has been marked as the current
 * login user.
 */
@Component({
  changeDetection: ChangeDetectionStrategy.Eager,standalone: false,
  selector: 'recovery-device-list',
  styleUrls: ['recovery_device_list.css'],
  templateUrl: './recovery_device_list.ng.html',
})
export class RecoveryDeviceList implements OnInit, OnChanges, OnDestroy {
  @ViewChild('table', {static: false, read: ElementRef}) table!: ElementRef;
  @ViewChild(MatTable, {static: true}) matTable!: MatTable<{}>;

  @Input() hostName!: string;
  @Input() selectedLab = '';
  @Output() readonly hide = new EventEmitter();

  private readonly destroy = new ReplaySubject<void>();

  deviceInfos: LabDeviceInfo[] = [];
  displayColumns: string[] = [
    'select',
    'device_serial',
    'run_target',
    'state',
    'last_checkin',
    'notes_update_time',
    'offline_reason',
    'note',
    'build_alias',
    'actions',
  ];
  isLoading = false;
  isTableScrolled = false;

  get deviceSerials() {
    return this.deviceInfos.map(info => info.device_serial);
  }

  @ViewChild(TableRowsSelectManager, {static: true})
  tableRowsSelectManager!: TableRowsSelectManager;

  constructor(
      private readonly dialog: MatDialog,
      private readonly liveAnnouncer: LiveAnnouncer,
      private readonly matDialog: MatDialog,
      private readonly notifier: Notifier,
      private readonly tfcClient: TfcClient,
      readonly userService: UserService,
  ) {}

  ngOnInit() {
    assertRequiredInput(this.matTable, 'matTable', 'RecoveryDeviceList');
    assertRequiredInput(
        this.tableRowsSelectManager, 'tableRowsSelectManager',
        'RecoveryDeviceList');
  }

  @HostListener('window:resize', [])
  onWindowResize() {
    this.checkTableScrolled();
  }

  ngOnChanges(changes: SimpleChanges) {
    if (changes['hostName']) {
      this.tableRowsSelectManager.selection.clear();
      this.tableRowsSelectManager.resetPrevClickedRowIndex();
      this.load();
    }
  }

  ngOnDestroy() {
    this.destroy.next();
  }

  load() {
    if (!this.isLoading) {
      this.isLoading = true;
      this.liveAnnouncer.announce('Loading', 'polite');
      this.tfcClient.getDeviceInfosFromHost(this.hostName)
          .pipe(
              takeUntil(this.destroy),
              finalize(() => {
                this.isLoading = false;
                this.checkTableScrolled();
              }),
              )
          .subscribe(
              (result) => {
                this.deviceInfos = result.deviceInfos || [];
                this.tableRowsSelectManager.rowIdFieldAllValues =
                    this.deviceSerials;
                if (this.deviceInfos.length > 0) {
                  this.getLatestNotes(this.deviceInfos);
                }
                this.liveAnnouncer.announce('Device list loaded', 'assertive');
              },
              (error) => {
                this.notifier.showError(
                    `Failed to load device list for host ${this.hostName}`);
              },
          );
    }
  }

  getLatestNotes(deviceInfos: LabDeviceInfo[]) {
    const deviceSerials = deviceInfos.map(info => info.device_serial);
    this.tfcClient.batchGetDevicesLatestNotes(deviceSerials)
        .pipe(takeUntil(this.destroy))
        .subscribe(
            (result) => {
              if (result && result.notes) {
                for (const note of result.notes) {
                  const deviceInfo = deviceInfos.find(
                      info => info.device_serial === note.device_serial);
                  if (deviceInfo) {
                    deviceInfo.latestNote = note;
                  }
                }
              }
            },
            (error) => {
              this.notifier.showError(
                  'Failed to load latest notes for devices');
            });
  }

  /** Check if table is scrolled to the right to update sticky styling. */
  checkTableScrolled() {
    const el = this.table.nativeElement;
    this.isTableScrolled = el.scrollLeft === el.scrollWidth - el.clientWidth;
  }

  /** Opens dialog for user to add device notes. */
  openDeviceNoteCreateEditor(
      event: MouseEvent, deviceInfos: LabDeviceInfo[] = []) {
    event.stopPropagation();

    if (!deviceInfos.length) {
      const selectedDeviceSerials =
          this.tableRowsSelectManager.selection.selected;
      deviceInfos = this.deviceInfos.filter((info) => {
        return selectedDeviceSerials.includes(info.device_serial);
      });
    }

    if (deviceInfos.length) {
      const params: NoteDialogParams = {
        dialogState: NoteDialogState.EDITOR,
        noteType: NoteType.DEVICE,
        ids: deviceInfos.map(info => info.device_serial),
        labName: this.selectedLab,
        deviceHostMap:
            deviceInfos.map(info => [info.device_serial, info.hostname || '']),
      };

      this.openNotesDialog(params)
          .afterClosed()
          .pipe(takeUntil(this.destroy))
          .subscribe(result => {
            if (result) {
              this.getLatestNotes(deviceInfos);
            }
          });
    } else {
      this.notifier.showError(`No device selected.`);
    }
  }

  /** Opens dialog for user to edit the latest device note. */
  openDeviceNoteUpdateEditor(event: MouseEvent, deviceInfo: LabDeviceInfo) {
    event.stopPropagation();
    if (deviceInfo.latestNote) {
      const params: NoteDialogParams = {
        dialogState: NoteDialogState.EDITOR,
        noteType: NoteType.DEVICE,
        ids: [deviceInfo.device_serial],
        noteId: deviceInfo.latestNote.id,
        labName: this.selectedLab,
        deviceHostMap: [[deviceInfo.device_serial, deviceInfo.hostname || '']],
      };

      this.openNotesDialog(params)
          .afterClosed()
          .pipe(takeUntil(this.destroy))
          .subscribe((result) => {
            if (result) {
              this.getLatestNotes([deviceInfo]);
            }
          });
    }
  }

  openNotesDialog(params: NoteDialogParams): MatDialogRef<NotesDialog> {
    return this.matDialog.open(NotesDialog, {
      height: '600px',
      width: '1200px',
      data: params,
      autoFocus: false,
    });
  }

  /** Opens a modal dialog to display the device related infos. */
  openDeviceDetailsDialog(event: Event, deviceSerial: string) {
    event.stopPropagation();
    const data: DeviceDetailsDialogParams = {id: deviceSerial, newWindow: true};
    this.dialog.open(DeviceDetails, {
      height: '700px',
      width: '1200px',
      data,
    });
  }

  /** Remove the device from the host. */
  removeDevice(event: Event, deviceSerial: string) {
    event.stopPropagation();
    this.tfcClient.removeDevice(deviceSerial, this.hostName)
        .pipe(takeUntil(this.destroy))
        .subscribe(
            () => {
              this.deviceInfos = this.deviceInfos.filter(
                  x => x.device_serial !== deviceSerial);
              this.tableRowsSelectManager.rowIdFieldAllValues =
                  this.deviceSerials;
              this.tableRowsSelectManager.resetSelection();
              this.matTable.renderRows();
              this.notifier.showMessage('Device removed');
            },
            () => {
              this.notifier.showError(
                  `Failed to remove device ${deviceSerial}`);
            });
  }
}
