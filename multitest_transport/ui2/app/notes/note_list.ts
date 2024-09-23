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
import {Component, ElementRef, EventEmitter, HostListener, Input, OnChanges, OnDestroy, OnInit, Output, SimpleChanges, ViewChild} from '@angular/core';
import {MatDialog} from '@angular/material/dialog';
import {ActivatedRoute, ParamMap, Router} from '@angular/router';
import {Notifier} from 'google3/third_party/py/multitest_transport/ui2/app/services/notifier';
import {DEFAULT_PAGE_SIZE, Paginator} from 'google3/third_party/py/multitest_transport/ui2/app/shared/paginator';
import {assertRequiredInput} from 'google3/third_party/py/multitest_transport/ui2/app/shared/util';
import {Observable, of as observableOf, OperatorFunction, pipe, ReplaySubject, throwError} from 'rxjs';
import {catchError, filter, finalize, map, switchMap, take, takeUntil} from 'rxjs/operators';

import {NoteDialogParams, NoteDialogState, NotesDialog} from '../notes/notes_dialog';
import {NoteType} from '../services/mtt_lab_models';
import {TfcClient} from '../services/tfc_client';
import {Note, NoteList as NoteListModel, NoteType as TfcNoteType} from '../services/tfc_models';
import {UserService} from '../services/user_service';

/** Display a list of notes from a device or a host. */
@Component({
  standalone: false,
  selector: 'note-list',
  styleUrls: ['note_list.css'],
  templateUrl: './note_list.ng.html',
})
export class NoteList implements OnChanges, OnInit, OnDestroy {
  @ViewChild('table', {static: true, read: ElementRef}) table!: ElementRef;
  @ViewChild(Paginator, {static: true}) paginator!: Paginator;

  private readonly destroy = new ReplaySubject<void>();
  noteList: Note[] = [];
  // A device serial or a hostname.
  @Input() id!: string;
  @Input() noteType!: NoteType;
  @Output() readonly showEditor = new EventEmitter<NoteDialogParams>();
  labName = '';
  /** Used for adding/editing a device note. */
  hostname?: string;
  includeDeviceNotes = true;

  readonly PAGE_SIZE_OPTIONS = [10, 20, 50];
  // Pagination tokens used to go backwards or forwards
  prevPageToken?: string;
  nextPageToken?: string;
  readonly NOTE_PAGE_SIZE = 'notePageSize';
  readonly NOTE_PAGE_TOKEN = 'notePageToken';
  readonly NOTE_URL_REWRITE = 'urlRewrite';
  readonly hostErrMsg = `Failed to load host note list for host ${this.id}`;
  readonly deviceErrMsg =
      `Failed to load device note list for device ${this.id}`;
  isTableScrolled = false;
  isHostNotes = false;

  displayedColumns: string[] = [
    'timestamp',
    'user',
    'offline_reason',
    'recovery_action',
    'message',
    'actions',
  ];
  isLoading = false;

  /** An observable that gets the query parameters from the URL. */
  protected readonly urlQueryParamObservable: Observable<ParamMap>;

  constructor(
      private readonly route: ActivatedRoute,
      private readonly liveAnnouncer: LiveAnnouncer,
      private readonly location: Location,
      private readonly matDialog: MatDialog,
      private readonly notifier: Notifier,
      private readonly router: Router,
      private readonly tfcClient: TfcClient,
      readonly userService: UserService,
  ) {
    this.urlQueryParamObservable = this.route.queryParamMap.pipe(take(1));
  }

  ngOnChanges(changes: SimpleChanges) {
    if (changes['id'] && !changes['id'].firstChange) this.loadNoteList();
  }

  ngOnInit() {
    assertRequiredInput(this.id, 'id', 'note-list');
    assertRequiredInput(this.noteType, 'noteType', 'note-list');
    this.isLoading = true;
    this.liveAnnouncer.announce('Loading', 'polite');
    this.urlQueryParamObservable
        .pipe(
            this.initPageTokensAndLab(),
            switchMap(
                () => this.noteType === NoteType.DEVICE ?
                    this.getDeviceNotes() :
                    this.getHostNotes()),
            takeUntil(this.destroy),
            )
        .subscribe(
            (result) => {
              this.noteList = result.notes || [];
              this.prevPageToken = result.prev_cursor;
              this.nextPageToken = result.next_cursor;
              this.refreshPaginator();
            },
            () => {
              const message = this.noteType === NoteType.DEVICE ?
                  this.deviceErrMsg :
                  this.hostErrMsg;
              this.notifier.showError(message);
            },
        );
  }

  getDeviceNotes(diff = 0, refresh = false): Observable<NoteListModel> {
    const pageToken = this.getPageToken(diff, refresh);
    return this.tfcClient
        .getDeviceNotes(
            this.id, [], this.paginator.pageSize, pageToken, diff === -1)
        .pipe(
            takeUntil(this.destroy),
            finalize(() => {
              this.isLoading = false;
              this.liveAnnouncer.announce(
                  'Device note list loaded', 'assertive');
            }),
        );
  }

  getHostNotes(diff = 0, refresh = false): Observable<NoteListModel> {
    const pageToken = this.getPageToken(diff, refresh);
    return this.tfcClient
        .getHostNotes(
            this.id, [], this.paginator.pageSize, pageToken, diff === -1,
            this.includeDeviceNotes)
        .pipe(
            takeUntil(this.destroy),
            finalize(() => {
              this.isLoading = false;
              this.liveAnnouncer.announce('Host note list loaded', 'assertive');
            }),
        );
  }

  /**
   * Gets the page token for query from backend api.
   * @param diff An indication to next or previous page. -1: previous page, 1:
   *     next page,  0: same page
   * @param refresh true to query current page from backend api
   */
  getPageToken(diff = 0, refresh = false): string|undefined {
    if (refresh) {
      return this.prevPageToken;
    }

    // paginator
    if (diff === -1) {
      return this.prevPageToken;
    } else if (diff === 1) {
      return this.nextPageToken;
    } else {
      return undefined;
    }
  }

  initPageTokensAndLab(): OperatorFunction<ParamMap, void> {
    return pipe(
        switchMap((params: ParamMap) => {
          const pageToken = params.get(this.NOTE_PAGE_TOKEN) || undefined;
          const pageSize = params.get(this.NOTE_PAGE_SIZE) ?
              Number(params.get(this.NOTE_PAGE_SIZE)) :
              DEFAULT_PAGE_SIZE;
          this.prevPageToken = undefined;
          this.nextPageToken = pageToken;
          this.paginator.pageSize = pageSize;
          return observableOf(null);
        }),
        switchMap(() => this.setLabName()),
    );
  }

  ngOnDestroy() {
    this.destroy.next();
  }

  loadNoteList(diff = 0, refresh = false) {
    this.noteType === NoteType.DEVICE ? this.loadDeviceNoteList(diff, refresh) :
                                        this.loadHostNoteList(diff, refresh);
  }

  /** Loads device note list with specified page. */
  loadDeviceNoteList(diff = 0, refresh = false) {
    this.getDeviceNotes(diff, refresh)
        .subscribe(
            result => {
              this.noteList = result.notes || [];
              this.prevPageToken = result.prev_cursor;
              this.nextPageToken = result.next_cursor;
              this.refreshPaginator();
            },
            error => {
              this.notifier.showError(this.deviceErrMsg);
            },
        );
  }

  /** Loads host note list with specified page. */
  loadHostNoteList(diff = 0, refresh = false) {
    this.getHostNotes(diff, refresh)
        .subscribe(
            result => {
              this.noteList = result.notes || [];
              this.prevPageToken = result.prev_cursor;
              this.nextPageToken = result.next_cursor;
              this.refreshPaginator();
            },
            error => {
              this.notifier.showError(this.hostErrMsg);
            },
        );
  }

  /** Page size change handler, will reload the first page of results. */
  resetPageTokenAndReload() {
    this.prevPageToken = undefined;
    this.nextPageToken = undefined;
    this.loadNoteList();
  }

  /** Open the Notes dialog to edit the note */
  editNote(
      noteId?: number,
      hostname?: string,
      deviceSerial?: string,
      noteType?: string,
  ) {
    let type = this.noteType;
    let id = this.id;
    if (noteType) {
      if (noteType === TfcNoteType.HOST_NOTE) {
        type = NoteType.HOST;
        id = hostname ?? '';
      } else {
        type = NoteType.DEVICE;
        id = deviceSerial ?? '';
      }
    }
    this.openEditor(noteId, id, type);
  }

  removeNote(
      noteId: number,
      noteType: string,
      hostname?: string,
      deviceSerial?: string,
  ) {
    this.notifier.confirm('', 'Remove note?', 'Remove note', 'Cancel')
        .pipe(
            filter(
                isConfirmed =>
                    isConfirmed !== false),  // Remove canceled confirmation.
            takeUntil(this.destroy),
            finalize(() => {
              this.isLoading = false;
            }),
            )
        .subscribe(() => {
          let id = this.id;
          if (noteType === TfcNoteType.HOST_NOTE) {
            id = hostname ?? '';
            this.removeHostNotes(id, noteId);
          } else {
            id = deviceSerial ?? '';
            this.removeDeviceNotes(id, noteId);
          }
        });
  }

  removeHostNotes(hostname: string, noteId: number) {
    this.tfcClient.batchDeleteHostNotes(hostname, [noteId])
        .pipe(takeUntil(this.destroy))
        .subscribe(
            () => {
              this.loadNoteList();
              this.notifier.showMessage('Host notes deleted');
            },
            () => {
              this.notifier.showError('Failed to delete host notes');
            });
  }

  removeDeviceNotes(deviceSerial: string, noteId: number) {
    this.tfcClient.batchDeleteDeviceNotes(deviceSerial, [noteId])
        .pipe(takeUntil(this.destroy))
        .subscribe(
            () => {
              this.loadNoteList();
              this.notifier.showMessage('Device notes deleted');
            },
            () => {
              this.notifier.showError('Failed to delete device notes');
            });
  }

  /** Pass data to parent component to display the editor. */
  openEditor(noteId?: number, id?: string, noteType?: NoteType) {
    const params: NoteDialogParams = {
      dialogState: NoteDialogState.EDITOR,
      noteType: noteType ?? this.noteType,
      ids: [id ? id : this.id],
      noteId,
      labName: this.labName,
      deviceHostMap: this.hostname ? [[id ? id : this.id, this.hostname]] : [],
    };
    this.matDialog
        .open(NotesDialog, {width: '1200px', height: '620px', data: params})
        .afterClosed()
        .pipe(takeUntil(this.destroy))
        .subscribe(result => {
          if (result === true) {
            if (noteId) {
              this.loadNoteList(0, true);
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
        'notePageToken': this.prevPageToken || null,
        'notePageSize': this.paginator.pageSize !== DEFAULT_PAGE_SIZE ?
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

  setLabName(): Observable<void> {
    if (this.noteType === NoteType.HOST) {
      this.isHostNotes = true;
      this.displayedColumns.splice(2, 0, 'note_type');
      this.displayedColumns.splice(3, 0, 'hostname_serial');
      return this.tfcClient.getHostInfo(this.id).pipe(
          map((result) => {
            this.labName = result.lab_name;
          }),
          catchError(err => {
            this.notifier.showError(`Failed to get host ${this.id}`);
            return throwError(err);
          }),
      );
    }

    return this.tfcClient.getDeviceInfo(this.id).pipe(
        map((result) => {
          this.labName = result.lab_name || '';
          this.hostname = result.hostname;
        }),
        catchError(err => {
          this.notifier.showError(`Failed to get device ${this.id}.`);
          return throwError(err);
        }),
    );
  }

  toggleDeviceNotes() {
    this.loadNoteList();
  }
}
