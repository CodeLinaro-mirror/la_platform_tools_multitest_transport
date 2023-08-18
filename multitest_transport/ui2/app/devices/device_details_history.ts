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
import {Component, Input, OnChanges, OnDestroy, OnInit, SimpleChanges, ViewChild} from '@angular/core';
import {MatDialog} from '@angular/material/dialog';
import {ActivatedRoute, Router} from '@angular/router';
import {Notifier} from 'google3/third_party/py/multitest_transport/ui2/app/services/notifier';
import {DEFAULT_PAGE_SIZE, Paginator} from 'google3/third_party/py/multitest_transport/ui2/app/shared/paginator';
import {assertRequiredInput} from 'google3/third_party/py/multitest_transport/ui2/app/shared/util';
import {ReplaySubject} from 'rxjs';
import {first, mergeMap, takeUntil} from 'rxjs/operators';

import {NoteDialogParams, NoteDialogState, NotesDialog} from '../notes/notes_dialog';
import {LabDeviceInfo, LabDeviceInfoHistoryList, NoteType} from '../services/mtt_lab_models';
import {TfcClient} from '../services/tfc_client';
import {UserService} from '../services/user_service';

/** Form for device history. */
@Component({
  selector: 'device-details-history',
  styleUrls: ['./device_details_history.css'],
  templateUrl: './device_details_history.ng.html',
})
export class DeviceDetailsHistory implements OnChanges, OnInit, OnDestroy {
  @Input() id!: string;
  private readonly destroy = new ReplaySubject<void>();
  isLoading = false;

  historyList: LabDeviceInfo[] = [];
  readonly PAGE_SIZE_OPTIONS = [10, 20, 50];
  // Pagination tokens used to go backwards or forwards
  prevPageToken?: string;
  nextPageToken?: string;
  readonly HISTORY_PAGE_SIZE = 'historyPageSize';
  readonly HISTORY_PAGE_TOKEN = 'historyPageToken';
  readonly HISTORY_URL_REWRITE = 'urlRewrite';

  displayedColumns: string[] = [
    'timestamp',
    'user',
    'offline_reason',
    'recovery_action',
    'message',
    'run_target',
    'state',
    'battery_level',
    'actions',
  ];

  @ViewChild(Paginator, {static: true}) paginator!: Paginator;

  constructor(
      private readonly location: Location,
      private readonly route: ActivatedRoute,
      private readonly liveAnnouncer: LiveAnnouncer,
      private readonly matDialog: MatDialog,
      private readonly notifier: Notifier,
      private readonly router: Router,
      private readonly tfcClient: TfcClient,
      readonly userService: UserService,
  ) {}

  ngOnChanges(changes: SimpleChanges) {
    if (changes['id'] && !changes['id'].firstChange) this.loadHistory(this.id);
  }

  ngOnInit() {
    assertRequiredInput(this.id, 'id', 'device-detail-history');
    this.route.queryParams.pipe(takeUntil(this.destroy)).subscribe(params => {
      const pageToken = params[this.HISTORY_PAGE_TOKEN];
      const pageSize = params[this.HISTORY_PAGE_SIZE] ?
          Number(params[this.HISTORY_PAGE_SIZE]) :
          DEFAULT_PAGE_SIZE;
      this.prevPageToken = undefined;
      this.nextPageToken = pageToken;
      this.paginator.pageSize = pageSize;
      this.loadHistory(this.id);
    });
  }

  ngOnDestroy() {
    this.destroy.next();
  }

  /**
   * Loads a page of deviceInfo history to the stored page tokens.
   * @param previous true to go to the previous page.
   */
  loadHistory(id: string, previous = false) {
    this.liveAnnouncer.announce('Loading', 'polite');
    this.isLoading = true;
    this.tfcClient
        .getDeviceHistory(
            id, this.paginator.pageSize,
            previous ? this.prevPageToken : this.nextPageToken, previous)
        .pipe(
            takeUntil(this.destroy),
            mergeMap((result: LabDeviceInfoHistoryList) => {
              // Step1: Get device history.
              this.historyList = result.histories || [];
              this.prevPageToken = result.prev_cursor;
              this.nextPageToken = result.next_cursor;
              const deviceNoteIds = this.getDeviceNoteIds(this.historyList);
              return this.tfcClient.batchGetDeviceNotes(id, deviceNoteIds);
            }))
        .subscribe(
            (result) => {
              // Step2: Merge device notes into deviceInfo.
              const notes = result.notes || [];
              for (const note of notes.filter(note => note !== undefined)) {
                const history = this.historyList.find(deviceInfo => {
                  return deviceInfo.extraInfo.device_note_id > 0 &&
                      deviceInfo.extraInfo.device_note_id === Number(note.id);
                });
                if (history) history.note = note;
              }
              this.isLoading = false;
              this.refreshPaginator();
              this.liveAnnouncer.announce('Device history loaded', 'assertive');
            },
            (error) => {
              this.notifier.showError('Failed to load device history list');
            },
        );
  }

  /** For paging event can invoke with the same id. */
  load(previous = false) {
    this.loadHistory(this.id, previous);
  }

  /** Page size change handler, will reload the first page of results. */
  resetPageTokenAndReload() {
    this.prevPageToken = undefined;
    this.nextPageToken = undefined;
    this.loadHistory(this.id, false);
  }

  /** Open the Notes dialog to edit the note */
  editNote(deviceNoteId: number) {
    this.openNoteDialog(deviceNoteId);
  }

  private openNoteDialog(deviceNoteId?: number) {
    const params: NoteDialogParams = {
      dialogState: NoteDialogState.EDITOR,
      noteType: NoteType.DEVICE,
      ids: [this.id],
      noteId: deviceNoteId,
      labName: this.historyList.length ? this.historyList[0].lab_name || '' :
                                         '',
    };
    this.matDialog
        .open(NotesDialog, {width: '1200px', height: '620px', data: params})
        .afterClosed()
        .pipe(takeUntil(this.destroy))
        .subscribe(result => {
          if (result === true) {
            if (deviceNoteId) {
              this.load();
            } else {
              this.resetPageTokenAndReload();
            }
          }
        });
  }

  /** Updates the paginator by latest query. */
  refreshPaginator() {
    // determine whether there are more results
    this.paginator.hasPrevious = !!this.prevPageToken;
    this.paginator.hasNext = !!this.nextPageToken;
    const urlTree = this.router.createUrlTree([], {
      queryParams: {
        'historyPageToken': this.prevPageToken || null,
        'historyPageSize': this.paginator.pageSize !== DEFAULT_PAGE_SIZE ?
            this.paginator.pageSize :
            null,
      },
      queryParamsHandling: 'merge',
    });
    this.location.replaceState(urlTree.toString());
  }

  /** Get deviceNoteIds from extra_info. */
  getDeviceNoteIds(historyList: LabDeviceInfo[]): number[] {
    return historyList.map((x) => Number(x.extraInfo.device_note_id))
        .filter(noteId => !isNaN(noteId) && noteId > 0);
  }
}
