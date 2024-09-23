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
import {Component, ElementRef, HostListener, Input, OnChanges, OnDestroy, OnInit, SimpleChanges, ViewChild} from '@angular/core';
import {MatDialog} from '@angular/material/dialog';
import {ActivatedRoute, Router} from '@angular/router';
import {ReplaySubject} from 'rxjs';
import {first, mergeMap, takeUntil} from 'rxjs/operators';

import {NoteDialogParams, NoteDialogState, NotesDialog} from '../notes/notes_dialog';
import {LabHostInfo, NoteType} from '../services/mtt_lab_models';
import {Notifier} from '../services/notifier';
import {TfcClient} from '../services/tfc_client';
import {UserService} from '../services/user_service';
import {DEFAULT_PAGE_SIZE, Paginator} from '../shared/paginator';
import {assertRequiredInput} from '../shared/util';

/** Displaying history list of a host. */
@Component({
  standalone: false,
  selector: 'host-details-history',
  styleUrls: ['./host_details_history.css'],
  templateUrl: './host_details_history.ng.html',
})
export class HostDetailsHistory implements OnChanges, OnDestroy, OnInit {
  @ViewChild('table', {static: true, read: ElementRef}) table!: ElementRef;
  @Input() id!: string;
  private readonly destroy = new ReplaySubject<void>();

  historyList: LabHostInfo[] = [];
  readonly PAGE_SIZE_OPTIONS = [10, 20, 50];
  // pagination tokens used to go backwards or forwards
  prevPageToken?: string;
  nextPageToken?: string;
  readonly HISTORY_PAGE_SIZE = 'historyPageSize';
  readonly HISTORY_PAGE_TOKEN = 'historyPageToken';
  readonly HISTORY_URL_REWRITE = 'urlRewrite';
  isTableScrolled = false;

  displayedColumns: string[] = [
    'timestamp',
    'user',
    'offline_reason',
    'recovery_action',
    'message',
    'state',
    'total',
    'online',
    'available',
    'utilization',
    'actions',
  ];

  @ViewChild(Paginator, {static: true}) paginator!: Paginator;

  constructor(
      private readonly route: ActivatedRoute,
      private readonly liveAnnouncer: LiveAnnouncer,
      private readonly location: Location,
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
    assertRequiredInput(this.id, 'id', 'host-details-history');
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
   * Loads a page of hostInfo history to the stored page tokens.
   * @param hostname Unique host name
   * @param previous true to go to the previous page
   */
  loadHistory(hostname: string, previous = false) {
    this.liveAnnouncer.announce('Loading', 'polite');
    this.tfcClient
        .getHostHistory(
            hostname, this.paginator.pageSize,
            previous ? this.prevPageToken : this.nextPageToken, previous)
        .pipe(
            takeUntil(this.destroy),
            mergeMap(
                result => {
                  // Step1: Get host history.
                  this.historyList = result.histories || [];
                  this.prevPageToken = result.prev_cursor;
                  this.nextPageToken = result.next_cursor;
                  const hostNoteIds =
                      this.historyList
                          .filter(
                              hostInfo => hostInfo && hostInfo.extraInfo &&
                                  hostInfo.extraInfo.host_note_id)
                          .map(hostInfo => hostInfo.extraInfo.host_note_id);
                  return this.tfcClient.batchGetHostNotes(
                      hostname, hostNoteIds);
                },
                ))
        .subscribe(
            result => {
              // Step2: Merge host notes into HostInfo.
              const notes = result.notes || [];
              for (const note of notes.filter(note => note !== undefined)) {
                const history = this.historyList.find((hostInfo) => {
                  return hostInfo.extraInfo &&
                      hostInfo.extraInfo.host_note_id === Number(note.id);
                });
                if (history) history.note = note;
              }
              this.refreshPaginator();
              this.liveAnnouncer.announce('Host history loaded', 'assertive');
            },
            (error) => {
              this.notifier.showError('Failed to load host history list');
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
  editNote(hostNoteId: number) {
    this.openNoteDialog(hostNoteId);
  }

  private openNoteDialog(hostNoteId?: number) {
    const params: NoteDialogParams = {
      dialogState: NoteDialogState.EDITOR,
      noteType: NoteType.HOST,
      ids: [this.id],
      noteId: hostNoteId,
      labName: this.historyList.length ? this.historyList[0].lab_name : '',
    };
    this.matDialog
        .open(NotesDialog, {width: '1200px', height: '620px', data: params})
        .afterClosed()
        .pipe(takeUntil(this.destroy))
        .subscribe(result => {
          if (result === true) {
            if (hostNoteId) {
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
    const urlTree = this.router.createUrlTree(['/hosts', this.id], {
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

  /** Check if table is scrolled to the right to update sticky styling. */
  checkTableScrolled() {
    const el = this.table.nativeElement;
    this.isTableScrolled = el.scrollLeft === el.scrollWidth - el.clientWidth;
  }

  @HostListener('window:resize', [])
  onWindowResize() {
    this.checkTableScrolled();
  }
}
