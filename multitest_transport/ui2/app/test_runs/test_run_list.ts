/**
 * Copyright 2019 Google LLC
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
import {COMMA, ENTER} from '@angular/cdk/keycodes';
import {AfterViewInit, Component, ElementRef, HostListener, OnDestroy, ViewChild} from '@angular/core';
import {MatChipInputEvent} from '@angular/material/chips';
import {MatTableDataSource} from '@angular/material/table';
import {ActivatedRoute, Router} from '@angular/router';
import {ReplaySubject} from 'rxjs';
import {finalize, first, takeUntil} from 'rxjs/operators';

import {MttClient} from '../services/mtt_client';
import {isFinalTestRunState, TableColumn, TestRunState, TestRunSummary} from '../services/mtt_models';
import {Notifier} from '../services/notifier';
import {OverflowListType} from '../shared/overflow_list';
import {DEFAULT_PAGE_SIZE, Paginator} from '../shared/paginator';
import {buildApiErrorMessage} from '../shared/util';

// Local storage key used to fetch visible columns
const COLUMN_DISPLAY_STORAGE_KEY = 'TEST_RUN_LIST_COLUMN_DISPLAY';

/** A component for displaying a list of test runs. */
@Component({
  standalone: false,
  selector: 'test-run-list',
  styleUrls: ['test_run_list.css'],
  templateUrl: './test_run_list.ng.html',
})
export class TestRunList implements AfterViewInit, OnDestroy {
  readonly PAGE_SIZE_OPTIONS = [10, 20, 50];
  readonly OverflowListType = OverflowListType;
  readonly SEPARATOR_KEYCODES: number[] = [ENTER, COMMA];
  readonly TEST_RUN_STATES: TestRunState[] = Object.values(TestRunState);

  // pagination tokens used to go backwards or forwards
  prevPageToken?: string;
  nextPageToken?: string;

  displayColumns = [
    'test_name', 'test_package', 'device_product', 'device_build',
    'device_specs', 'labels', 'create_time', 'status', 'view'
  ];

  columns: TableColumn[] = [
    {
      fieldName: 'select',
      displayName: '',
      removable: false,
      show: true,
    },
    {
      fieldName: 'test_name',
      displayName: 'Test',
      removable: false,
      show: true,
    },
    {
      fieldName: 'test_package',
      displayName: 'Test Package',
      removable: true,
      show: true
    },
    {
      fieldName: 'device_product',
      displayName: 'Product',
      removable: true,
      show: true
    },
    {
      fieldName: 'device_build',
      displayName: 'Device Build',
      removable: true,
      show: true
    },
    {
      fieldName: 'device_specs',
      displayName: 'Device Specs',
      removable: true,
      show: true
    },
    {
      fieldName: 'labels',
      displayName: 'Labels',
      removable: true,
      show: true,
    },
    {
      fieldName: 'create_time',
      displayName: 'Created',
      removable: true,
      show: true
    },
    {
      fieldName: 'status',
      displayName: 'Status',
      removable: false,
      show: true,
    },
    {
      fieldName: 'failures',
      displayName: 'Test Failures',
      removable: false,
      show: true
    },
    {
      fieldName: 'view',
      displayName: 'View',
      removable: false,
      show: true,
    },
  ];

  isLoading = false;
  dataSource = new MatTableDataSource<TestRunSummary>([]);
  filters: string[] = [];
  states: TestRunState[] = [];
  isFinalTestRunState = isFinalTestRunState;

  selection = new SelectionModel<TestRunSummary>(
      /*allow multi select*/ true, []);

  @ViewChild('table', {static: false, read: ElementRef}) table!: ElementRef;
  isTableScrolled = false;

  @ViewChild(Paginator, {static: false}) paginator!: Paginator;

  private readonly destroy = new ReplaySubject<void>();

  constructor(
      private readonly notifier: Notifier, private readonly mtt: MttClient,
      private readonly route: ActivatedRoute, private readonly router: Router,
      private readonly liveAnnouncer: LiveAnnouncer) {}

  ngAfterViewInit() {
    // handle asynchronously to prevent modifying view in ngAfterViewInit
    setTimeout(() => this.route.queryParams.pipe(first()).subscribe(params => {
      // initialize results based on query parameters
      this.prevPageToken = undefined;
      this.nextPageToken = params['page'];
      this.paginator.pageSize = Number(params['size']) || DEFAULT_PAGE_SIZE;
      this.filters = params['filter'] ? [].concat(params['filter']) : [];
      this.states = (params['state'] ? [].concat(params['state']) : [])
                        .filter(s => this.TEST_RUN_STATES.includes(s));
      this.load(false);
      // initialize display columns
      this.loadDisplayColumnFromLocalStorage();
      this.setDisplayColumn();
    }));
  }

  ngOnDestroy() {
    this.destroy.next();
  }

  @HostListener('window:resize', [])
  onWindowResize() {
    this.checkTableScrolled();
  }

  /**
   * Loads a page of test runs according to the stored page tokens.
   * @param previous true to go to the previous page
   */
  load(previous = false) {
    this.isLoading = true;
    this.liveAnnouncer.announce('Loading', 'polite');
    this.selection.clear();
    this.mtt
        .getTestRuns(
            this.paginator.pageSize,
            previous ? this.prevPageToken : this.nextPageToken, previous,
            this.filters, this.states)
        .pipe(
            takeUntil(this.destroy),
            finalize(() => {
              this.isLoading = false;
            }),
            )
        .subscribe(
            result => {
              this.dataSource.data = result.test_runs || [];
              this.prevPageToken = result.prev_page_token || undefined;
              this.nextPageToken = result.next_page_token || undefined;
              this.updatePageParams();
              this.liveAnnouncer.announce('Test results loaded', 'assertive');
            },
            error => {
              this.notifier.showError(
                  'Failed to load test run list.', buildApiErrorMessage(error));
            },
        );
  }

  /** Updates the paginator and stores its parameters in the query string. */
  private updatePageParams() {
    // determine whether there are more results
    this.paginator.hasPrevious = !!this.prevPageToken;
    this.paginator.hasNext = !!this.nextPageToken;
    // store pagination parameters
    this.router.navigate([], {
      queryParams: {
        page: this.prevPageToken || null,
        size: this.paginator.pageSize !== DEFAULT_PAGE_SIZE ?
            this.paginator.pageSize :
            null,
        filter: this.filters.length > 0 ? this.filters : null,
        state: this.states.length > 0 ? this.states : null,
      }
    });
  }

  /** Page size change handler, will reload the first page of results. */
  resetPageTokenAndReload() {
    this.prevPageToken = undefined;
    this.nextPageToken = undefined;
    this.load(false);
  }

  /** Reload the current page of runs. */
  reload() {
    this.nextPageToken = this.prevPageToken;
    this.prevPageToken = undefined;
    this.load(false);
  }

  /** Check if table is scrolled to the right to update sticky styling. */
  checkTableScrolled() {
    const el = this.table.nativeElement;
    this.isTableScrolled = el.scrollLeft === el.scrollWidth - el.clientWidth;
  }

  /* Update column display data */
  toggleDisplayColumn(event: Event, show: boolean, columnIndex: number) {
    event.stopPropagation();
    this.columns[columnIndex].show = !show;
    this.setDisplayColumn();
  }

  /* Apply column display data */
  private setDisplayColumn() {
    this.displayColumns =
        this.columns.filter(c => c.show).map(c => c.fieldName);
    this.storeDisplayColumnToLocalStorage();
    setTimeout(() => {
      this.checkTableScrolled();
    });
  }

  /* Store column display data to local storage */
  storeDisplayColumnToLocalStorage() {
    window.localStorage.setItem(
        COLUMN_DISPLAY_STORAGE_KEY, JSON.stringify(this.columns));
  }

  /* Loading column display data from local storage if there is any */
  private loadDisplayColumnFromLocalStorage() {
    const storedData = window.localStorage.getItem(COLUMN_DISPLAY_STORAGE_KEY);

    if (storedData) {
      const storedTableColumns = JSON.parse(storedData) as TableColumn[];
      this.columns = this.columns.map((c) => {
        const storedColumn =
            storedTableColumns.find((s) => s.fieldName === c.fieldName);
        if (storedColumn) {
          c.show = storedColumn.show;
        }
        return c;
      });
    }
  }

  /* Add input to chips and reload */
  addFilter(event: MatChipInputEvent) {
    const input = event.chipInput.inputElement;
    const value = (event.value || '').trim();

    if (value && !this.filters.includes(value)) {
      this.filters.push(value);
      this.resetPageTokenAndReload();
    }

    if (input) {
      input.value = '';
    }
  }

  /* Remove filter and reload */
  removeFilter(filter: string) {
    const index = this.filters.indexOf(filter);
    if (index >= 0) {
      this.filters.splice(index, 1);
      this.resetPageTokenAndReload();
    }
  }

  /**
   * Whether the number of selected elements matches the total number of rows.
   */
  isAllSelected() {
    let count = 0;
    for (const row of this.dataSource.data) {
      if (isFinalTestRunState(row.state)) {
        count++;
      }
    }
    return this.selection.selected.length === count;
  }

  /**
   * Selects all rows if they are not all selected; otherwise clear selection.
   */
  toggleSelection() {
    if (this.isAllSelected()) {
      this.selection.clear();
      return;
    }

    for (const row of this.dataSource.data) {
      if (isFinalTestRunState(row.state)) {
        this.selection.select(row);
      }
    }
  }

  /** Returns true if all test run states are final, false otherwise. */
  validateSelectedRowDeletion() {
    for (const summary of this.selection.selected) {
      if (!isFinalTestRunState(summary.state)) {
        return false;
      }
    }
    return true;
  }

  deleteSelectedRows() {
    this.notifier
        .confirm(
            'Do you really want to delete these test runs?', 'Delete Test Runs')
        .subscribe(result => {
          if (!result) {
            return;
          }
          this.isLoading = true;
          this.mtt
              .deleteTestRuns(
                  this.selection.selected.map(testRun => testRun.id!))
              .pipe(
                  finalize(() => {
                    this.reload();
                  }),
                  )
              .subscribe(
                  (res) => {
                    this.notifier.showMessage('Test runs deleted.');
                  },
                  (error) => {
                    this.notifier.showError(
                        'Failed to delete test runs.',
                        buildApiErrorMessage(error));
                  });
        });
  }
}
