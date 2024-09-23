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
import {Component, ElementRef, HostListener, OnDestroy, OnInit, ViewChild} from '@angular/core';
import {MatDialog} from '@angular/material/dialog';
import {MatTable, MatTableDataSource} from '@angular/material/table';
import {MatSort, Sort} from '@angular/material/sort';
import {Notifier} from 'google3/third_party/py/multitest_transport/ui2/app/services/notifier';
import {assertRequiredInput} from 'google3/third_party/py/multitest_transport/ui2/app/shared/util';
import {Observable, of as observableOf, ReplaySubject, throwError} from 'rxjs';
import {catchError, concatMap, filter, finalize, map, switchMap, takeUntil} from 'rxjs/operators';

import {covertToPredefinedMessageType, MessageCategory, MessageType} from '../services/mtt_lab_models';
import {TfcClient} from '../services/tfc_client';
import {PredefinedMessage, PredefinedMessageType} from '../services/tfc_models';
import {UserService} from '../services/user_service';

import {PredefinedMessagesEditor} from './predefined_messages_editor';

/**
 * Data format for storing the parameters associated with the filters.
 */
export declare interface FilterParams {
  lab: string;
  messageCategory: string;
  messageType: string;
}

/** Possible value filed for browser to set localStorage. */
export type SingleValueField = 'lab'|'messageCategory'|'messageType';

/** Display list of predefined message. */
@Component({
  standalone: false,
  selector: 'predefined-message-list',
  styleUrls: ['predefined_message_list.css'],
  templateUrl: './predefined_message_list.ng.html',
})
export class PredefinedMessageList implements OnInit, OnDestroy {
  @ViewChild('table', {static: true, read: ElementRef}) table!: ElementRef;
  @ViewChild(MatTable, {static: false}) matTable!: MatTable<{}>;
  @ViewChild(MatSort, {static: true}) matSort!: MatSort;

  private readonly defaultFilterParams = {
    lab: '',
    messageCategory: '',
    messageType: '',
  };

  tableDataSource = new MatTableDataSource<PredefinedMessage>([]);
  get dataSource() {
    return this.tableDataSource.data;
  }
  labs: string[] = [];
  messageCategories: string[] = [];
  messageTypes: string[] = [];
  displayedColumns = [
    'content',
    'type',
    'create_timestamp',
    'used_count',
    'actions',
  ];
  isLoading = false;
  isTableScrolled = false;

  selectedLab = this.defaultFilterParams.lab;
  selectedMessageCategory = this.defaultFilterParams.messageCategory;
  selectedMessageType = this.defaultFilterParams.messageType;

  private readonly destroy = new ReplaySubject<void>();

  readonly FILTER_CRITERIA_STORAGE_KEY =
      'PREDEFINED_MESSAGE_LIST_FILTER_CRITERIA';
  private readonly LAB_FIELD = 'lab';
  private readonly MESSAGE_CATEGORY_FIELD = 'messageCategory';
  private readonly MESSAGE_TYPE_FIELD = 'messageType';

  // TODO: Predefined message CRUD.

  constructor(
      private readonly matDialog: MatDialog,
      private readonly liveAnnouncer: LiveAnnouncer,
      private readonly notifier: Notifier,
      private readonly tfcClient: TfcClient,
      readonly userService: UserService,
  ) {}

  ngOnInit() {
    assertRequiredInput(this.table, 'table', 'mat-table');
    this.tableDataSource.sort = this.matSort;
    this.messageCategories = Object.values(MessageCategory);
    this.messageTypes = Object.values(MessageType);
    this.load();
  }

  ngOnDestroy() {
    this.destroy.next();
  }

  load() {
    this.isLoading = true;
    this.liveAnnouncer.announce('Loading', 'polite');

    // Set selectors default value.
    this.initMessageCategorySelection();
    this.initMessageTypeSelection();

    this.tfcClient.getLabInfos()
        .pipe(
            takeUntil(this.destroy),
            finalize(() => {
              this.isLoading = false;
              this.liveAnnouncer.announce('Loading complete', 'assertive');
              this.checkTableScrolled();
              this.updateLocalStorage();
            }),
            map((result) => {
              this.labs = result.labInfos.map(labInfo => labInfo.labName);
              this.initLabSelection();
              return this.selectedLab;
            }),
            concatMap((selectedLab) => {
              const predefinedMessageType =
                  this.getCurrentPredefinedMessageType();
              if (selectedLab && predefinedMessageType) {
                return this.predefinedMessagesObservable(
                    selectedLab, predefinedMessageType);
              } else {
                return observableOf([]);
              }
            }),
            )
        .subscribe(
            (result) => {
              this.tableDataSource.data = result;
            },
            () => {
              this.notifier.showError(
                  'Failed to load lab and predefined message list');
            });
  }

  reloadPredefinedMessages() {
    const predefinedMessageType = this.getCurrentPredefinedMessageType();
    if (this.selectedLab && predefinedMessageType) {
      this.isLoading = true;
      this.liveAnnouncer.announce('Loading', 'polite');
      this.predefinedMessagesObservable(this.selectedLab, predefinedMessageType)
          .pipe(takeUntil(this.destroy), finalize(() => {
                  this.isLoading = false;
                  this.liveAnnouncer.announce('Loading complete', 'assertive');
                  this.checkTableScrolled();
                }))
          .subscribe(
              (result) => {
                this.tableDataSource.data = result;
              },
              () => {
                this.notifier.showError(
                    'Failed to load predefined message list');
              });
    }
    this.updateLocalStorage();
  }

  predefinedMessagesObservable(
      selectedLab: string,
      predefinedMessageType: PredefinedMessageType|
      undefined): Observable<PredefinedMessage[]> {
    if (!selectedLab || !predefinedMessageType) {
      return observableOf([]);
    }
    return this.tfcClient
        .getPredefinedMessages(selectedLab, predefinedMessageType)
        .pipe(
            map(result => result.predefined_messages || []),
        );
  }

  deletePredefinedMessage(id: number) {
    this.notifier.confirm('', 'Remove message?', 'Remove message', 'Cancel')
        .pipe(
            switchMap((result) => {
              if (!result) return observableOf(false);
              return this.tfcClient.deletePredefinedMessage(id).pipe(
                  catchError((err) => throwError(err)),
              );
            }),
            filter(
                isConfirmed =>
                    isConfirmed !== false),  // Remove canceled confirmation.
            takeUntil(this.destroy),
            )
        .subscribe(
            () => {
              // Remove deleted predefined message from
              // this.predefinedMessages.
              this.tableDataSource.data =
                  this.tableDataSource.data.filter(x => x.id !== id);
              this.matTable.renderRows();
              this.notifier.showMessage('Predefined message deleted');
            },
            () => {
              this.notifier.showError('Failed to delete predefined message');
            });
  }

  /** Initializes the options of lab filter. */
  initLabSelection() {
    this.selectedLab = this.getFilterDefaultValue(this.LAB_FIELD, this.labs);
  }

  /** Initializes the options of category filter. */
  initMessageCategorySelection() {
    this.selectedMessageCategory = this.getFilterDefaultValue(
        this.MESSAGE_CATEGORY_FIELD, this.messageCategories);
  }

  /** Initializes the options of message type filter. */
  initMessageTypeSelection() {
    this.selectedMessageType =
        this.getFilterDefaultValue(this.MESSAGE_TYPE_FIELD, this.messageTypes);
  }

  /**
   * Gets the default value for a filter. The value could be specified from
   * last selected value stored in local storage or the first value of the
   * options.
   */
  getFilterDefaultValue(filterField: SingleValueField, options: string[]):
      string {
    const storedParam = this.loadFromLocalStorage()[filterField];

    if (options.includes(storedParam)) {
      return storedParam;
    }

    if (options.length) {
      return options[0];
    }

    return this.defaultFilterParams[filterField];
  }

  /** Saves last criteria data to localstorage. */
  updateLocalStorage() {
    window.localStorage.setItem(
        this.FILTER_CRITERIA_STORAGE_KEY, JSON.stringify({
          lab: this.selectedLab,
          messageCategory: this.selectedMessageCategory,
          messageType: this.selectedMessageType,
        } as FilterParams));
  }

  /** Loads last criteria data from local storage if exists. */
  loadFromLocalStorage(): FilterParams {
    const storedData =
        window.localStorage.getItem(this.FILTER_CRITERIA_STORAGE_KEY);
    return storedData ? JSON.parse(storedData) as FilterParams :
                        this.defaultFilterParams;
  }

  /**
   * Converts selected category and message type into predefined message type.
   */
  getCurrentPredefinedMessageType(): PredefinedMessageType|undefined {
    return covertToPredefinedMessageType(
        this.selectedMessageCategory, this.selectedMessageType);
  }

  /** Check if table is scrolled to the right to update sticky styling. */
  checkTableScrolled() {
    const el = this.table.nativeElement;
    this.isTableScrolled = el.scrollLeft === el.scrollWidth - el.clientWidth;
  }

  /** Clicks header to sort. */
  changeSort(sortInfo: Sort) {
    this.matSort.active = sortInfo.active;
    this.matSort.direction = sortInfo.direction;
  }

  @HostListener('window:resize', [])
  onWindowResize() {
    this.checkTableScrolled();
  }

  openPredefinedMessagesEditor(predefinedMessage?: PredefinedMessage) {
    this.matDialog
        .open(PredefinedMessagesEditor, {
          height: '500px',
          width: '1200px',
          data: {
            predefinedMessage,
            defaultMessageCategory: this.selectedMessageCategory,
            defaultMessageType: this.selectedMessageType,
            defaultLab: this.selectedLab,
          },
        })
        .afterClosed()
        .pipe(
            takeUntil(this.destroy),
            )
        .subscribe(this.editorCloseHandler(predefinedMessage));
  }

  editorCloseHandler(predefinedMessage?: PredefinedMessage) {
    return (result: PredefinedMessage|undefined) => {
      if (result) {
        const tempData = this.tableDataSource.data;
        if (predefinedMessage) {  // Update existed predefined message.
          const itemIndex = tempData.findIndex(x => x.id === result.id);
          tempData[itemIndex] = result;
        } else {  // Add new predfined message.
          tempData.unshift(result);
        }
        this.tableDataSource.data = tempData;
        this.matTable.renderRows();
      }
    };
  }
}
