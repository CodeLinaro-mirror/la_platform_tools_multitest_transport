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
import {Component, ElementRef, OnDestroy, OnInit, ViewChild, ChangeDetectionStrategy} from '@angular/core';
import {UntypedFormControl, UntypedFormGroup} from '@angular/forms';
import {MatAutocomplete, MatAutocompleteTrigger} from '@angular/material/autocomplete';
import {MatDialog} from '@angular/material/dialog';
import {MatTable} from '@angular/material/table';
import {ActivatedRoute, ParamMap, Router} from '@angular/router';
import {forkJoin, Observable, of as observableOf, ReplaySubject, throwError} from 'rxjs';
import {catchError, concatMap, delay, filter, finalize, map, mergeMap, retryWhen, switchMap, take, takeUntil} from 'rxjs/operators';

import {FeedbackService} from '../services/feedback_service';
import {FilterOption, HostQueryParams, HostSearchCriteria, LAB_STORAGE_KEY, LabHostInfo, LabHostInfosResponse, SurveyTrigger} from '../services/mtt_lab_models';
import {TableColumn} from '../services/mtt_models';
import {Notifier} from '../services/notifier';
import {StorageService} from '../services/storage_service';
import {TfcClient} from '../services/tfc_client';
import {FilterHintList, FilterHintType, TestHarness} from '../services/tfc_models';
import {UserService} from '../services/user_service';
import {FilterBarUtility} from '../shared/filterbar_util';
import {OverflowListType} from '../shared/overflow_list';
import {DEFAULT_PAGE_SIZE, Paginator} from '../shared/paginator';
import {assertRequiredInput} from '../shared/util';

import {HostUpdateDialog, HostUpdateDialogData} from './host_update_dialog';

/** Displaying a list of hosts. */
@Component({
  changeDetection: ChangeDetectionStrategy.Eager,standalone: false,
  selector: 'host-list',
  styleUrls: ['host_list.css'],
  templateUrl: './host_list.ng.html',
})
export class HostList implements OnDestroy, OnInit {
  isLoading = false;
  private readonly destroy = new ReplaySubject<void>();
  dataSource: LabHostInfo[] = [];

  @ViewChild('table', {static: true, read: ElementRef}) table!: ElementRef;
  @ViewChild(MatTable, {static: true}) matTable!: MatTable<{}>;
  isTableScrolled = false;
  readonly overflowListType = OverflowListType;
  readonly testHarness = TestHarness;
  displayColumns = [
    'hostname',
    'host_group',
    'host_state',
    'run_target',
    'pools',
    'testHarness',
    'testHarnessVersion',
    'updateState',
    'lab',
    'total',
    'online',
    'available',
    'utilization',
    'actions',
  ];
  columns: TableColumn[] = [
    {
      fieldName: 'hostname',
      displayName: 'Hostname',
      removable: false,
      show: true
    },
    {
      fieldName: 'host_group',
      displayName: 'Host Group',
      removable: true,
      show: true
    },
    {
      fieldName: 'host_state',
      displayName: 'Host State',
      removable: true,
      show: true
    },
    {
      fieldName: 'run_target',
      displayName: 'Run Targets',
      removable: true,
      show: true
    },
    {fieldName: 'pools', displayName: 'Pools', removable: true, show: true},
    {
      fieldName: 'testHarness',
      displayName: 'Test Harness',
      removable: true,
      show: true
    },
    {
      fieldName: 'testHarnessVersion',
      displayName: 'Test Harness Version',
      removable: true,
      show: true
    },
    {
      fieldName: 'updateState',
      displayName: 'Update State',
      removable: true,
      show: true
    },
    {fieldName: 'lab', displayName: 'Lab', removable: true, show: true},
    {fieldName: 'total', displayName: 'Total', removable: true, show: true},
    {fieldName: 'online', displayName: 'Online', removable: true, show: true},
    {
      fieldName: 'available',
      displayName: 'Available',
      removable: true,
      show: true
    },
    {
      fieldName: 'utilization',
      displayName: 'Utilization',
      removable: true,
      show: true
    },
    {fieldName: 'actions', displayName: 'Actions', removable: true, show: true},
  ];
  readonly columnDisplayStorageKey = 'HOST_LIST_COLUMN_DISPLAY';

  @ViewChild(Paginator, {static: true}) paginator!: Paginator;
  // Pagination tokens used to go backwards or forwards
  prevPageToken?: string;
  nextPageToken?: string;
  readonly hostListPageSize = 'hostListPageSize';
  readonly hostListPageToken = 'hostListPageToken';
  readonly all = 'All';
  readonly allSize = 10000;
  readonly pageSizeOptions = [10, 50, 100, 500, 1000, this.allSize];

  labs: string[] = [];
  selectedLab = '';

  filterBarUtility!: FilterBarUtility;
  @ViewChild('valueInput', {static: true}) valueInput!: ElementRef;
  @ViewChild('valueInput', {static: true, read: MatAutocompleteTrigger})
  matAutocompleteTrigger!: MatAutocompleteTrigger;
  @ViewChild('auto', {static: true}) matAutocomplete!: MatAutocomplete;
  valueControl = new UntypedFormControl({value: ''});
  formGroup = new UntypedFormGroup({
    'valueControl': this.valueControl,
  });
  readonly searchableColumns = new Map<string, FilterHintType>([
    ['Host Group', FilterHintType.HOST_GROUP],
    ['Hostname', FilterHintType.HOST],
    ['Pool', FilterHintType.POOL],
    ['State', FilterHintType.HOST_STATE],
    ['Test Harness', FilterHintType.TEST_HARNESS],
    ['Test Harness Version', FilterHintType.TEST_HARNESS_VERSION],
    ['Update State', FilterHintType.UPDATE_STATE],
  ]);
  readonly extraInfoDisplay = 'Extra Info';
  readonly extraInfoParamName = 'extraInfo';
  readonly labParamName = 'lab';
  readonly back = 'Back';
  readonly searchCriteriaStorageKey = 'HostListSearchCriteria';
  sessionStorageKey = '';

  private readonly urlQueryParamObservable: Observable<ParamMap>;

  get inputValue(): string {
    return this.valueControl.value || '';
  }

  /**
   * The string value users typed in the last cycle.  A 'Cycle' means the user
   * press Enter, Tab or Click a option on the menu. Cycle 1: Types a column
   * name. e.g.'Pool'+ Enter, 'Pool' is returned. Once the cycle is handled by
   * the submit method, the after value of 'searchCriteriaSnapshot' and
   * 'selectedColumn' will be both 'Pool' in this case. Cycle 2: The value of
   * the textbox is 'Pool' then the user types a value. e.g.
   * '(Pool-1)'+ Enter, '(Pool-1)' is returned. Once the cycle is handled by the
   * submit method, the after value of 'searchCriteriaSnapshot' will be 'Pool:
   * (Pool-1)' and  'selectedColumn' will be empty in this case.
   */
  get lookupColumnValue(): string {
    return this.inputValue
        .replace(this.filterBarUtility.searchCriteriaSnapshot, '')
        .replace(`${this.filterBarUtility.selectedColumn}:`, '');
  }

  get filteredOptions() {
    return this.filterBarUtility.getVisibleFilterOptions();
  }

  get isRoot(): boolean {
    return this.filterBarUtility.isRoot();
  }

  get hasFilter(): boolean {
    return this.filterBarUtility.hasFilter();
  }

  constructor(
      private readonly feedbackService: FeedbackService,
      private readonly liveAnnouncer: LiveAnnouncer,
      private readonly location: Location,
      private readonly notifier: Notifier,
      private readonly router: Router,
      private readonly route: ActivatedRoute,
      private readonly storageService: StorageService,
      private readonly tfcClient: TfcClient,
      private readonly matDialog: MatDialog,
      readonly userService: UserService,
  ) {
    this.urlQueryParamObservable = this.route.queryParamMap.pipe(take(1));
  }

  ngOnInit() {
    assertRequiredInput(this.paginator, 'paginator', 'host-list');
    assertRequiredInput(this.table, 'table', 'host-list');
    assertRequiredInput(this.valueInput, 'valueInput', 'host-list');
    assertRequiredInput(
        this.matAutocompleteTrigger, 'matAutocompleteTrigger', 'host-list');
    assertRequiredInput(this.matAutocomplete, 'matAutocomplete', 'host-list');
    assertRequiredInput(this.matTable, 'matTable', 'host-list');

    this.setFilterBarParameters();
    this.initFilterBarThenLoad();
    this.loadDisplayColumnFromLocalStorage();
    this.setDisplayColumn();
    this.valueControl.valueChanges.pipe(takeUntil(this.destroy))
        .subscribe(() => {
          this.filterBarUtility.filterSearchOptions(
              this.lookupColumnValue, this.filterBarUtility.selectedColumn);
        });
    this.clearInput();
  }

  setFilterBarParameters() {
    const filterBarColumns = [
      'Host Group',
      'Hostname',
      'Pool',
      'State',
      'Test Harness',
      'Test Harness Version',
      'Update State',
      this.extraInfoDisplay,
    ];

    // The mapping of display(column) name and parameter name.
    const searchCriteriaMapping = new Map<string, string>([
      ['Host Group', 'hostGroups'],
      ['Hostname', 'hostnames'],
      ['Lab', 'lab'],
      ['Pool', 'pools'],
      ['State', 'hostStates'],
      ['Test Harness', 'testHarness'],
      ['Test Harness Version', 'testHarnessVersions'],
      ['Update State', 'hostUpdateStates'],
      [this.extraInfoDisplay, this.extraInfoParamName],
    ]);

    this.filterBarUtility = new FilterBarUtility(
        [], filterBarColumns, searchCriteriaMapping, 30, 'type', 1,
        [this.extraInfoDisplay]);
  }

  /** Initializes all criteria for the filterbar then bind table. */
  initFilterBarThenLoad() {
    this.isLoading = true;
    this.filterBarUtility.initFilterbarRoots();
    forkJoin([
      this.getLabObservable(),
      this.getFilterHintObservable(FilterHintType.HOST),
      this.getFilterHintObservable(FilterHintType.HOST_GROUP),
      this.getFilterHintObservable(FilterHintType.HOST_STATE),
      this.getFilterHintObservable(FilterHintType.POOL),
      this.getFilterHintObservable(FilterHintType.TEST_HARNESS),
      this.getFilterHintObservable(FilterHintType.TEST_HARNESS_VERSION),
      this.getFilterHintObservable(FilterHintType.UPDATE_STATE),
    ])
        .pipe(
            retryWhen((errors) => errors.pipe(delay(500), take(3))),
            mergeMap(() => this.urlQueryParamObservable),
            concatMap((params) => this.updatePaginatorParamsAndLoad(params)),
            takeUntil(this.destroy),
            finalize(() => {
              this.isLoading = false;
            }),
            )
        .subscribe(
            (result) => {
              this.afterDataloaded(result);
            },
            () => {
              this.notifier.showError('Failed to load host list');
            });
  }

  getLabObservable(): Observable<null> {
    return this.tfcClient.getFilterHintList(FilterHintType.LAB)
        .pipe(
            mergeMap((result) => {
              this.labs = result.filter_hints?.map((item) => item.value);
              return this.urlQueryParamObservable;
            }),
            mergeMap((params) => {
              this.selectedLab = params.get(this.labParamName) || '';
              if (!this.selectedLab) {
                this.selectedLab = this.loadSelectedLabFromLocalStorage();
              }
              return observableOf(null);
            }),
            retryWhen((errors) => errors.pipe(delay(500), take(3))),
            takeUntil(this.destroy),
        );
  }

  getFilterHintObservable(filterHintType: FilterHintType): Observable<null> {
    // Try load from sessionStorage.
    const items = window.sessionStorage.getItem(String(filterHintType));
    if (items) {
      const result = JSON.parse(items) as FilterOption[];
      this.filterBarUtility.appendFilterOptions(result);
      return observableOf(null);
    } else {
      // First time or not found will load from api.
      return this.tfcClient.getFilterHintList(filterHintType)
          .pipe(
              map((result) => this.convertToFilterOptions(
                      result, String(filterHintType))),
              mergeMap((result) => {
                this.filterBarUtility.appendFilterOptions(result);
                window.sessionStorage.setItem(
                    String(filterHintType), JSON.stringify(result));
                return observableOf(null);
              }),
              retryWhen((errors) => errors.pipe(delay(500), take(3))),
              takeUntil(this.destroy),
          );
    }
  }

  updatePaginatorParamsAndLoad(params: ParamMap):
      Observable<LabHostInfosResponse> {
    const pageToken = params.get(this.hostListPageToken) || '';
    const sizeString = params.get(this.hostListPageSize) || DEFAULT_PAGE_SIZE;
    const sizeNumber = Number(sizeString);
    const pageSize =
        !isNaN(sizeNumber) && this.pageSizeOptions.includes(sizeNumber) ?
        sizeNumber :
        DEFAULT_PAGE_SIZE;
    this.prevPageToken = undefined;
    this.nextPageToken = pageToken;
    this.paginator.pageSize = pageSize;
    this.paginator.showPageIndex = true;

    const disabledLoadFromLocalStorage = this.hasQueryStringParams(params);
    for (const type of this.searchableColumns.values()) {
      this.setFilterHintSelectedValues(
          type, params, !disabledLoadFromLocalStorage);
    }
    this.loadNonFilterHintTypeCriteria(params);
    this.renderSelectedOptions();
    const searchResult = window.sessionStorage.getItem(this.sessionStorageKey);
    if (searchResult) {
      const data = JSON.parse(searchResult) as LabHostInfosResponse;
      return observableOf(data);
    } else {
      this.isLoading = true;
      return this.tfcClient
          .getHostInfos(
              this.getSearchCriteria(), this.paginator.pageSize, pageToken)
          .pipe(takeUntil(this.destroy));
    }
  }

  hasQueryStringParams(params: ParamMap): boolean {
    return params.keys.length > 0;
  }

  /** Loads extraInifo from query string and localstorage. */
  loadNonFilterHintTypeCriteria(params: ParamMap) {
    let extraInfo = params.get(this.extraInfoParamName);
    if (!extraInfo) {
      extraInfo = this.getSearchCriteriaFromLocalStorageByProperty(
          this.extraInfoParamName)[0];
    }
    if (extraInfo) this.addInputOption(extraInfo);
  }

  /** Loads values from queryString or localStorage then set selected. */
  setFilterHintSelectedValues(
      filterHintType: FilterHintType, queryParams: ParamMap,
      enableLoadFromLocalStorage: boolean) {
    const columnName = this.getColumnName(filterHintType);
    const paraName = this.filterBarUtility.getParameterName(columnName) || '';
    let values = queryParams.getAll(paraName) || [];
    if ((!values || values.length === 0) && enableLoadFromLocalStorage) {
      values = this.getSearchCriteriaFromLocalStorage(filterHintType);
    }
    this.filterBarUtility.setFilterOptionsSelected(columnName, values);
  }

  clearInput() {
    this.valueControl.reset();
  }

  backToRoot(event: KeyboardEvent|MouseEvent) {
    event.stopImmediatePropagation();
    this.filterBarUtility.selectedColumn = '';
    this.renderSelectedOptions();
    this.filterBarUtility.displayRootFilterOptions();
  }

  /** Selects single item on the search results. */
  toggleSelection(event: KeyboardEvent|MouseEvent, option: FilterOption) {
    event.stopImmediatePropagation();
    event.preventDefault();
    // Root
    if (option.type === this.filterBarUtility.rootColumnType) {
      // List some kind of options. e.g. hostStates.
      this.filterBarUtility.displayLeafFilterOptions(option.value);
      this.renderSelectedOptions(option.value);
      setTimeout(() => {
        this.matAutocomplete._setScrollTop(0);
      }, 0);
    } else {
      this.filterBarUtility.toggleFilterOption(option);
    }
  }

  /** Selects all filtered items. */
  toggleSelectAll(event?: KeyboardEvent|MouseEvent) {
    if (event) {
      event.stopImmediatePropagation();
      event.preventDefault();
    }
    this.filterBarUtility.toggleAll();
  }

  getSearchCriteriaFromLocalStorage(type: FilterHintType): string[] {
    const columnName = this.getColumnName(type);
    return this.getSearchCriteriaFromLocalStorageByProperty(
        this.filterBarUtility.getParameterName(columnName) || '');
  }

  getSearchCriteriaFromLocalStorageByProperty(propertyName: string): string[] {
    const searchCriteria = this.loadSearchCriteriaFromLocalStorage();
    for (const [key, value] of Object.entries(searchCriteria)) {
      if (key === propertyName) {
        return value;
      }
    }
    return [];
  }

  convertToFilterOptions(
      filterHintList: FilterHintList, filterHintType: string): FilterOption[] {
    const filterHints = filterHintList.filter_hints || [];
    const columnName = this.getColumnName(filterHintType);
    return this.filterBarUtility.createFilterOptions(
        filterHints.filter(x => x && x.value).map(x => x.value), columnName,
        true, true);
  }

  /** Gets search criteria display name. */
  getColumnName(filterHintType: string): string {
    for (const [key, value] of this.searchableColumns.entries()) {
      if (filterHintType === value) return key;
    }
    return '';
  }

  ngOnDestroy() {
    this.destroy.next();
  }

  resetSearchSteps() {
    this.filterBarUtility.resetSearchSteps();
  }

  submit(event: KeyboardEvent) {
    const triggrtByAutoComplete =
        !!this.matAutocompleteTrigger.activeOption?.value;
    if (triggrtByAutoComplete) {
      if (!this.isRoot) {
        const value = this.matAutocompleteTrigger.activeOption?.value;
        this.dispatchHandler(value, event);
        if (value !== this.back) {
          this.matAutocompleteTrigger.closePanel();
        }
      } else {
        if (this.filterBarUtility.isRootColumn(this.inputValue)) {
          this.dispatchHandler(this.inputValue, event);
        }
        // Click a root node on the autocomplete option.
        else if (
            this.inputValue !== '' ||
            this.filterBarUtility.searchCriteriaSnapshot === '') {
          this.toggleByKeyPressed(event);
        }
      }
    } else {
      // edit input text
      // Type a column name then press enter on the input. i.e. pool+Enter. The
      // menu should display the options belong to the 'Pool' and keep the menu
      // opening.
      if (this.filterBarUtility.isRootColumn(this.lookupColumnValue) ||
          this.filterBarUtility.isEditingInputColumn()) {
        this.dispatchHandler(this.lookupColumnValue, event);
      } else if (
          this.filterBarUtility.searchCriteriaSnapshot !== this.inputValue) {
        this.parseInputValue(this.inputValue);
        this.matAutocompleteTrigger.closePanel();
        this.load();
        this.filterBarUtility.searchCriteriaSnapshot = this.inputValue;
      }
      this.renderSelectedOptions();

      if (this.matAutocomplete.isOpen) {
      }
    }
    this.startHostFilterBarHats();
  }

  load(diff = 0, forceRefresh = false) {
    this.isLoading = true;
    this.resetSearchSteps();
    this.liveAnnouncer.announce('Loading', 'polite');
    const previous = diff === -1;
    if (!diff) {
      this.paginator.resetPageIndex();
    }
    const pageToken = this.getPageToken(diff, forceRefresh);
    const searchCriteria = this.getSearchCriteria();
    this.setSessionStorageKey();
    const searchResult = window.sessionStorage.getItem(this.sessionStorageKey);
    this.patchQueryParams();
    if (searchResult && !forceRefresh) {
      this.afterDataloaded(
          JSON.parse(searchResult) as LabHostInfosResponse, true);
    } else {
      this.tfcClient
          .getHostInfos(searchCriteria, this.getPageSize(), pageToken, previous)
          .pipe(
              takeUntil(this.destroy),
              )
          .subscribe(
              (result) => {
                this.afterDataloaded(result);
              },
              () => {
                this.notifier.showError('Failed to load host list');
              });
    }
  }

  /**
   * Gets the page token for query from backend api.
   * @param diff An indication to next or previous page. -1: previous page, 1:
   *     next page,  0: same page
   * @param forceRefresh true to always query from backend api
   */
  getPageToken(diff = 0, forceRefresh = false): string|undefined {
    // forceRefresh: always refresh current page.
    if (forceRefresh) {
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

  setSessionStorageKey() {
    const searchCriteria = this.getSearchCriteria();
    this.sessionStorageKey = `${JSON.stringify(searchCriteria)}-${
        String(this.getPageSize())}-${String(this.paginator.pageIndex)}`;
  }

  /** Handles the api returns data and switch status. */
  afterDataloaded(result: LabHostInfosResponse, isFromSessionStorage = false) {
    this.dataSource = result.host_infos || [];
    this.prevPageToken = result.prevCursor;
    this.nextPageToken = result.nextCursor;
    this.isLoading = false;
    this.filterBarUtility.filterChanged = false;
    this.refreshPaginator();
    this.liveAnnouncer.announce('Host list loaded', 'assertive');
    if (!isFromSessionStorage) {
      window.sessionStorage.setItem(
          this.sessionStorageKey, JSON.stringify(result));
    }
  }

  getPageSize(): number {
    return this.paginator.pageSize;
  }

  getSearchCriteria(): HostSearchCriteria {
    const searchCriteria: HostSearchCriteria = {};
    if (this.selectedLab) {
      searchCriteria.lab = this.selectedLab;
    }
    if (this.getSelectedOptions(FilterHintType.HOST)) {
      searchCriteria.hostnames = this.getSelectedOptions(FilterHintType.HOST);
    }
    if (this.getSelectedOptions(FilterHintType.HOST_GROUP)) {
      searchCriteria.hostGroups =
          this.getSelectedOptions(FilterHintType.HOST_GROUP);
    }
    if (this.getSelectedOptions(FilterHintType.TEST_HARNESS)) {
      searchCriteria.testHarness =
          this.getSelectedOptions(FilterHintType.TEST_HARNESS);
    }
    if (this.getSelectedOptions(FilterHintType.TEST_HARNESS_VERSION)) {
      searchCriteria.testHarnessVersions =
          this.getSelectedOptions(FilterHintType.TEST_HARNESS_VERSION);
    }
    if (this.getSelectedOptions(FilterHintType.POOL)) {
      searchCriteria.pools = this.getSelectedOptions(FilterHintType.POOL);
    }
    if (this.getSelectedOptions(FilterHintType.HOST_STATE)) {
      searchCriteria.hostStates =
          this.getSelectedOptions(FilterHintType.HOST_STATE);
    }
    if (this.getSelectedOptions(FilterHintType.UPDATE_STATE)) {
      searchCriteria.hostUpdateStates =
          this.getSelectedOptions(FilterHintType.UPDATE_STATE);
    }
    searchCriteria.extraInfo =
        [this.filterBarUtility.getInputFilterOption(this.extraInfoDisplay)];

    return searchCriteria;
  }

  /** Gets run targets from the dataSource. */
  getRunTargets(host: LabHostInfo): string[] {
    return host.device_count_summaries ?
        host.device_count_summaries.map(x => x.run_target) :
        [];
  }

  getPools(host: LabHostInfo): string[] {
    return host.pools ? host.pools : [];
  }

  /** Checks if table is scrolled to the right to update sticky styling. */
  checkTableScrolled() {
    const el = this.table.nativeElement;
    this.isTableScrolled = el.scrollLeft === el.scrollWidth - el.clientWidth;
  }

  /** Reloads the first page of results. */
  resetPageTokenAndReload() {
    this.prevPageToken = undefined;
    this.nextPageToken = undefined;
    this.load();
  }

  /** Updates the paginator by latest query. */
  refreshPaginator() {
    // determine whether there are more results
    this.paginator.hasPrevious = !!this.prevPageToken;
    this.paginator.hasNext = !!this.nextPageToken;
    this.patchQueryParams();
    this.saveSearchCriteriaToLocalStorage();
    this.saveSelectedLabToLocalStorage();
  }

  /** Patches parameters to query string. */
  patchQueryParams() {
    const queryParams = this.getQueryParamsFromOptions();
    const urlTree = this.router.createUrlTree([], {
      queryParams,
      queryParamsHandling: 'merge',
    });
    this.location.replaceState(urlTree.toString());
  }

  getQueryParamsFromOptions(): HostQueryParams {
    const queryParams: HostQueryParams = {};
    if (this.selectedLab) {
      queryParams.lab = this.selectedLab;
    }
    if (this.getSelectedOptions(FilterHintType.HOST)) {
      queryParams.hostnames = this.getSelectedOptions(FilterHintType.HOST);
    }
    if (this.getSelectedOptions(FilterHintType.HOST_GROUP)) {
      queryParams.hostGroups =
          this.getSelectedOptions(FilterHintType.HOST_GROUP);
    }
    if (this.getSelectedOptions(FilterHintType.TEST_HARNESS)) {
      queryParams.testHarness =
          this.getSelectedOptions(FilterHintType.TEST_HARNESS);
    }
    if (this.getSelectedOptions(FilterHintType.TEST_HARNESS_VERSION)) {
      queryParams.testHarnessVersions =
          this.getSelectedOptions(FilterHintType.TEST_HARNESS_VERSION);
    }
    if (this.getSelectedOptions(FilterHintType.POOL)) {
      queryParams.pools = this.getSelectedOptions(FilterHintType.POOL);
    }
    if (this.getSelectedOptions(FilterHintType.HOST_STATE)) {
      queryParams.hostStates =
          this.getSelectedOptions(FilterHintType.HOST_STATE);
    }
    if (this.prevPageToken) {
      queryParams.hostListPageToken = this.prevPageToken;
    }
    if (this.paginator.pageSize !== DEFAULT_PAGE_SIZE) {
      queryParams.hostListPageSize = this.paginator.pageSize;
    }
    queryParams.extraInfo =
        [this.filterBarUtility.getInputFilterOption(this.extraInfoDisplay)];

    return queryParams;
  }

  getSelectedOptions(type: FilterHintType): string[]|undefined {
    const columnName = this.getColumnName(String(type));
    const selectedOptions =
        this.filterBarUtility.getFilterOptions(columnName, true)
            .map(x => x.value);
    return selectedOptions.length ? selectedOptions : undefined;
  }

  /** When host state is GONE, user can remove(hide) the host. */
  removeHost(hostname: string) {
    this.notifier.confirm('', 'Remove host?', 'Remove host', 'Cancel')
        .pipe(
            switchMap((result) => {
              if (!result) return observableOf(false);
              return this.tfcClient.removeHost(hostname).pipe(
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
              this.dataSource =
                  this.dataSource.filter(x => x.hostname !== hostname);
              this.matTable.renderRows();
              this.notifier.showMessage(`Host '${hostname}' removed`);
              this.load(0, true);
            },
            () => {
              this.notifier.showError(`Failed to remove host
                    ${hostname}`);
            });
  }

  /**
   * The tab key was pressed on one of the filter options
   * or in the text field.
   */
  toggleByKeyPressed(event: KeyboardEvent) {
    event.preventDefault();
    if (!this.matAutocompleteTrigger.activeOption) {
      this.matAutocompleteTrigger.closePanel();
      return;
    }
    const value = this.matAutocompleteTrigger.activeOption.value;
    this.dispatchHandler(value, event);
  }

  dispatchHandler(selectedValue: string, event: KeyboardEvent) {
    if (selectedValue === this.back) {
      this.backToRoot(event);
      return;
    } else if (selectedValue === this.all) {
      // Leaf item clicked select all
      this.toggleSelectAll(event);
      return;
    }

    // At root, pressed tab/enter. load leaf
    // At leaf, pressed tab. select the leaf item.
    // At leaf, pressed enter. select the leaf item and submit.
    let type = this.filterBarUtility.selectedColumn;
    if (this.isRoot && this.filterBarUtility.isRootColumn(selectedValue)) {
      selectedValue =
          this.filterBarUtility.getFilterBarColumnName(selectedValue);
      this.filterBarUtility.selectedColumn = selectedValue;
      type = this.filterBarUtility.rootColumnType;
    } else if (this.filterBarUtility.isEditingInputColumn()) {
      // Not in searchable columns, search on the extra info.
      this.addInputOption(selectedValue);
      return;
    }
    const filterOption =
        this.filterBarUtility.getFilterOption(type, selectedValue);
    this.toggleSelection(event, filterOption);
  }

  getFilterOption(type: string, value: string, selected: boolean = false):
      FilterOption {
    return this.filteredOptions.find(
               x => x.type === type && x.value === value) ||
        {
          value,
          selected,
          type,
          hidden: false,
          showCheckbox: false,
        };
  }

  /** Displays the selected filters and reset filterbar. */
  renderSelectedOptionsAndResetFilterbar() {
    this.renderSelectedOptions();
    this.resetSearchSteps();
    this.valueInput.nativeElement.blur();
    if (this.filterBarUtility.filterChanged) this.load();
  }

  /** Displays the selected filters. */
  renderSelectedOptions(columnName: string = '') {
    let selectedOptionsString = this.filterBarUtility.getSelectedOptionString();
    if (columnName &&
        this.filterBarUtility.getFilterOptions(columnName, true).length === 0) {
      selectedOptionsString = `${selectedOptionsString} ${columnName}:`;
    }
    this.setSelectedOptionsString(selectedOptionsString);
  }

  setSelectedOptionsString(selectedOptionsString: string) {
    this.filterBarUtility.searchCriteriaSnapshot = selectedOptionsString;
    this.filterBarUtility.innerUpdate = true;
    this.valueControl.setValue(selectedOptionsString);
  }

  resetSelection() {
    this.filterBarUtility.resetFilterOptions();
    this.setSelectedOptionsString('');
    this.filterBarUtility.filterChanged = true;
    this.matAutocompleteTrigger.closePanel();
    this.renderSelectedOptionsAndResetFilterbar();
  }

  loadSelectedLabFromLocalStorage(): string {
    return window.localStorage.getItem(LAB_STORAGE_KEY) || '';
  }

  loadSearchCriteriaFromLocalStorage(): HostSearchCriteria {
    const criteria = window.localStorage.getItem(this.searchCriteriaStorageKey);
    return criteria ? JSON.parse(criteria) as HostSearchCriteria : {
      lab: '',
      hostnames: [],
      hostGroups: [],
      testHarness: [],
      testHarnessVersions: [],
      pools: [],
      hostStates: [],
      extraInfo: [],
    };
  }

  saveSearchCriteriaToLocalStorage() {
    window.localStorage.setItem(
        this.searchCriteriaStorageKey,
        JSON.stringify(this.getSearchCriteria()));
  }

  saveSelectedLabToLocalStorage() {
    window.localStorage.setItem(LAB_STORAGE_KEY, this.selectedLab);
  }

  toggleDisplayColumn(event: Event, show: boolean, columnIndex: number) {
    event.stopPropagation();
    this.columns[columnIndex].show = !show;
    this.setDisplayColumn();
  }

  private setDisplayColumn() {
    this.displayColumns =
        this.columns.filter(c => c.show).map(c => c.fieldName);
    this.updateDisplayColumnToLocalStorage();
    setTimeout(() => {
      this.checkTableScrolled();
    });
  }

  updateDisplayColumnToLocalStorage() {
    window.localStorage.setItem(
        this.columnDisplayStorageKey, JSON.stringify(this.columns));
  }

  loadDisplayColumnFromLocalStorage() {
    const storedData =
        window.localStorage.getItem(this.columnDisplayStorageKey);
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

  /** Naviagte to host details page. */
  openHostDetails(hostName: string) {
    const hostnames = this.dataSource.map(x => x.hostname);
    this.storageService.hostList = hostnames;
    const url = this.getHostDetailsUrl(hostName);
    this.router.navigateByUrl(url);
  }

  getHostDetailsUrl(hostName: string) {
    const url = this.router.serializeUrl(
        this.router.createUrlTree(['/hosts', hostName]));
    return url;
  }

  storeHostNamesInLocalStorage() {
    const hostnames = this.dataSource.map(x => x.hostname);
    this.storageService.saveHostListInLocalStorage(hostnames);
  }

  /** Updates input criteria to the filterOptions. */
  parseInputValue(inputValue: string) {
    for (const columnName of this.filterBarUtility.filterBarColumns) {
      const section =
          this.filterBarUtility.extractSection(inputValue, columnName);
      inputValue = inputValue.replace(section, '').trim();
      const inputOptions = this.filterBarUtility.extractValues(section);

      if (this.filterBarUtility.columnsWithNoPreloadedOptions.includes(
              columnName)) {
        if (inputOptions && inputOptions.length === 1 &&
            inputOptions[0] !== '') {
          this.addInputOption(inputOptions[0]);
        } else if (inputOptions.length > 1) {
          this.notifier.showWarning(
              `'${columnName}' only supports single value`);
        }
      } else if (this.filterBarUtility.isSelectedFilterOptionsMatchInputValues(
                     inputOptions, columnName)) {
        this.filterBarUtility.applySelection(inputOptions, columnName);
      }
    }
    if (inputValue.trim()) {
      this.notifier.showWarning(`Unknown filter: ${inputValue.trim()}`);
    }
  }

  /**
   * The searching value(extrInfo) comes from user input.
   */
  addInputOption(value: string) {
    if (value.indexOf(':') > -1 || value.indexOf('=') > -1) {
      const columnName =
          this.filterBarUtility.columnsWithNoPreloadedOptions[0];  // Extra Info
      this.filterBarUtility.addNewFilterOption(value, columnName);
    } else {
      this.notifier.showError('Incorrect format. The format is "key:value"');
    }
  }

  startHostFilterBarHats() {
    this.feedbackService.startSurvey(SurveyTrigger.HOST_FILTER_BAR);
  }

  openHostUpdateDialog() {
    const data: HostUpdateDialogData = {
      selectedLab: this.selectedLab,
    };
    this.matDialog.open(HostUpdateDialog, {
      height: '600px',
      width: '1250px',
      data,
      autoFocus: true,
    });
  }
}
