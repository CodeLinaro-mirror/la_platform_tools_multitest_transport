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
import {SelectionModel} from '@angular/cdk/collections';
import {AfterViewInit, Component, ElementRef, EventEmitter, HostListener, Input, OnChanges, OnDestroy, Output, SimpleChanges, ViewChild} from '@angular/core';
import {MatDialog} from '@angular/material/dialog';
import {MatTable} from '@angular/material/table';
import {Notifier} from 'google3/third_party/py/multitest_transport/ui2/app/services/notifier';
import {ReplaySubject} from 'rxjs';
import {finalize, takeUntil} from 'rxjs/operators';

import {HostDetails, HostDetailsDialogParams} from '../hosts/host_details';
import {ALL_OPTIONS_VALUE, filterHostListDataSource} from '../hosts/offline_host_filter';
import {NoteDialogParams, NoteDialogState, NotesDialog} from '../notes/notes_dialog';
import {LabHostInfo, NoteType} from '../services/mtt_lab_models';
import {TfcClient} from '../services/tfc_client';
import {HostRecoveryStateRequest, RecoveryState} from '../services/tfc_models';
import {UserService} from '../services/user_service';
import {buildApiErrorMessage} from '../shared/util';

/** Display a list of host that are recovering by the current user. */
@Component({
  standalone: false,
  selector: 'recovery-host-list',
  styleUrls: ['recovery_host_list.css'],
  templateUrl: './recovery_host_list.ng.html',
})
export class RecoveryHostList implements AfterViewInit, OnChanges, OnDestroy {
  @ViewChild('table', {static: false, read: ElementRef}) table!: ElementRef;
  @ViewChild(MatTable, {static: false}) matTable!: MatTable<{}>;

  @Input() focusedHostName = '';
  @Input() hostInfos: LabHostInfo[] = [];
  @Input() initialSelection = [];
  @Input() selectedHostGroups: string[] = [];
  @Input() selectedLab = '';
  @Input() selectedRunTargets: string[] = [];
  @Output() readonly focusedHostNameChange = new EventEmitter<string>();
  @Output() readonly selectionChange = new EventEmitter<string[]>();

  private readonly destroy = new ReplaySubject<void>();

  collapseDisplayColumns = ['select', 'hostname'];
  expandDisplayColumns = [
    'select',
    'hostname',
    'host_group',
    'host_state',
    'offline_devices',
    'last_checkin',
    'actions',
  ];
  displayColumns: string[] = this.expandDisplayColumns;
  hostNameMap: {[hostname: string]: LabHostInfo} = {};
  isLoading = false;
  isTableScrolled = false;
  selection = new SelectionModel<string>(true, this.initialSelection);
  readonly ALL_OPTIONS_VALUE = 'All';

  constructor(
      private readonly dialog: MatDialog,
      private readonly liveAnnouncer: LiveAnnouncer,
      private readonly matDialog: MatDialog,
      private readonly notifier: Notifier,
      private readonly tfcClient: TfcClient,
      readonly userService: UserService,
  ) {}

  @HostListener('window:resize', [])
  onWindowResize() {
    this.checkTableScrolled();
  }

  ngAfterViewInit() {
    // Handle asynchronously to prevent modifying view in ngAfterViewInit.
    setTimeout(() => {
      this.load();
    });
  }

  ngOnChanges(changes: SimpleChanges) {
    if (changes['focusedHostName']) {
      this.displayColumns = changes['focusedHostName'].currentValue ?
          this.collapseDisplayColumns :
          this.expandDisplayColumns;
    }
  }

  ngOnDestroy() {
    this.destroy.next();
  }

  // TODO: Filter run target in frontend.
  load() {
    if (!this.isLoading) {
      this.isLoading = true;
      this.liveAnnouncer.announce('Loading', 'polite');
      this.tfcClient
          .getMyRecoveryHostInfos(
              this.selectedLab,
              this.selectedHostGroups.includes(ALL_OPTIONS_VALUE) ?
                  [] :
                  this.selectedHostGroups)  // If 'All' options selected should
                                            // pass an empty string array.
          .pipe(
              takeUntil(this.destroy),
              finalize(() => {
                this.isLoading = false;
                this.checkTableScrolled();
              }),
              )
          .subscribe(
              (result) => {
                if (result.host_infos) {
                  this.hostInfos = filterHostListDataSource(
                      result.host_infos, this.selectedHostGroups,
                      this.selectedRunTargets);
                }
                this.hostNameMap = this.infosToHostNameMap(this.hostInfos);
                this.liveAnnouncer.announce('Host list loaded', 'assertive');
              },
              (error) => {
                this.notifier.showError(
                    'Failed to load recovery host list.',
                    buildApiErrorMessage(error));
              },
          );
    }
  }

  /** Mark a list of host as in done recovery state. */
  markAsRecovered(
      event: MouseEvent, selectedHost: string[] = this.selection.selected) {
    event.stopPropagation();
    let hostNames = selectedHost;
    if (this.focusedHostName) {
      hostNames = [this.focusedHostName];
    }
    const hostRecoveryStateRequests = hostNames.map(hostname => {
      return {
        hostname,
        recovery_state: RecoveryState.VERIFIED,
      } as HostRecoveryStateRequest;
    });

    if (hostNames.length > 0) {
      this.tfcClient.batchSetHostsRecoveryStates(hostRecoveryStateRequests)
          .pipe(
              takeUntil(this.destroy),
              )
          .subscribe(
              () => {
                // Remove recovered hosts from this.hostInfos.
                this.hostInfos =
                    this.hostInfos.filter(x => !hostNames.includes(x.hostname));
                this.matTable.renderRows();
                this.selection.clear();
                this.notifier.showMessage('Hosts marked as recovered');
              },
              () => {
                this.notifier.showError('Failed to mark hosts as recovered');
              });
    }
  }

  /** Converts an array of LabHostInfos to a map indexed by host name. */
  infosToHostNameMap(infos: LabHostInfo[]): {[hostname: string]: LabHostInfo} {
    const serialMap: {[hostname: string]: LabHostInfo} = {};
    return infos.reduce((map, info) => {
      map[info.hostname] = info;
      return map;
    }, serialMap);
  }

  /** Check if table is scrolled to the right to update sticky styling. */
  checkTableScrolled() {
    const el = this.table.nativeElement;
    this.isTableScrolled = el.scrollLeft === el.scrollWidth - el.clientWidth;
  }

  /** Displays device list from provided host and clears the selection. */
  focusHost(hostName: string) {
    this.focusedHostName = hostName;
    this.selection.clear();
    this.focusedHostNameChange.emit(this.focusedHostName);
  }

  isFocusedRow(hostName: string): boolean {
    return this.focusedHostName === hostName;
  }

  /** Toggle the corresponding row and emit the selected hosts. */
  onSelectionChange(hostName: string) {
    this.selection.toggle(hostName);
    if (this.selection.selected.length > 0) {
      this.focusedHostName = '';
      this.focusedHostNameChange.emit(this.focusedHostName);
    }
    this.selectionChange.emit(this.selection.selected);
  }

  /** Returns true if a host name has been selected, false otherwise. */
  hasSelectedHostName(): boolean {
    for (const target of this.selection.selected) {
      if (this.hostNameMap[target]) {
        return true;
      }
    }
    return false;
  }

  /**
   * Whether the number of selected elements matches the total number of rows.
   */
  isAllSelected() {
    const numSelected = this.selection.selected.length;
    const numRows = this.hostInfos && this.hostInfos.length;
    return numSelected === numRows;
  }

  /**
   * Selects all rows if they are not all selected; otherwise clear selection
   * and focused host.
   */
  toggleSelection() {
    if (this.isAllSelected()) {
      this.selection.clear();
    } else {
      for (const host of this.hostInfos) {
        this.selection.select(host.hostname);
      }
    }

    if (this.selection.selected.length > 0) {
      this.focusedHostName = '';
      this.focusedHostNameChange.emit(this.focusedHostName);
    }
    this.selectionChange.emit(this.selection.selected);
  }

  /**
   * Returns text to display in host group or run target chip base on the length
   * of selected.
   * @return String to display on chip.
   */
  multiSelectedDisplay(selected: string[]): string {
    if (selected.length === 0 || selected.includes(this.ALL_OPTIONS_VALUE)) {
      return this.ALL_OPTIONS_VALUE;
    } else if (selected.length === 1) {
      return selected[0];
    }
    return `${selected.length} selected`;
  }

  /** Opens dialog for user to add host notes. */
  openHostNoteCreateEditor(
      event: MouseEvent, hostNames: string[] = this.selection.selected) {
    event.stopPropagation();

    const params: NoteDialogParams = {
      dialogState: NoteDialogState.EDITOR,
      noteType: NoteType.HOST,
      ids: hostNames,
      labName: this.selectedLab,
    };
    this.openNotesDialog(params);
  }

  /** Opens dialog for user to edit the latest host note. */
  openHostNoteUpdateEditor(event: MouseEvent, hostName: string) {
    event.stopPropagation();

    // Load the host note list and open editor for the latest note.
    this.tfcClient.getHostNotes(hostName, [], 1)
        .pipe(
            takeUntil(this.destroy),
            )
        .subscribe(
            (result) => {
              if (result.notes &&
                  result.notes.length >
                      0) {  // Open the latest note in edit mode.
                const params: NoteDialogParams = {
                  dialogState: NoteDialogState.EDITOR,
                  noteType: NoteType.HOST,
                  ids: [hostName],
                  noteId: result.notes[0].id,
                  labName: this.selectedLab,
                };
                this.openNotesDialog(params);
              } else {
                this.notifier.showError(`No note found for host ${hostName}`);
              }
            },
            (error) => {
              this.notifier.showError(
                  `Failed to load host ${hostName} note`,
                  buildApiErrorMessage(error));
            },
        );
  }

  openNotesDialog(params: NoteDialogParams) {
    this.matDialog.open(NotesDialog, {
      height: '600px',
      width: '1200px',
      data: params,
      autoFocus: false,
    });
  }

  /** Opens a modal dialog to display the host related infos. */
  openHostDetails(event: Event, hostName: string) {
    event.stopPropagation();
    const data: HostDetailsDialogParams = {id: hostName, newWindow: true};
    this.dialog.open(HostDetails, {
      height: '700px',
      width: '1200px',
      data,
    });
  }
}
