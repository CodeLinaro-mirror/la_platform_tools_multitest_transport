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
import {Component, ElementRef, EventEmitter, Inject, Input, OnChanges, OnDestroy, OnInit, Output, SimpleChanges, ViewChild} from '@angular/core';
import {UntypedFormControl, UntypedFormGroup} from '@angular/forms';
import {MatAutocomplete, MatAutocompleteTrigger} from '@angular/material/autocomplete';
import {MatTable} from '@angular/material/table';
import {ActivatedRoute, convertToParamMap, ParamMap, Router} from '@angular/router';
import {forkJoin, Observable, of as observableOf, ReplaySubject, throwError, timer} from 'rxjs';
import {catchError, concatMap, delay, filter, map, mergeMap, retryWhen, switchMap, take, takeUntil} from 'rxjs/operators';

import {APP_DATA, AppData} from '../services';
import {FeedbackService} from '../services/feedback_service';
import {ALL_OPTIONS_VALUE, DEVICE_SERIAL, DeviceQueryParams, DeviceSearchCriteria, FilterOption, HOSTNAME, LAB_STORAGE_KEY, LabDeviceInfo, LabDeviceInfosResponse, REMOVE_DEVICE_MESSAGE, SurveyTrigger} from '../services/mtt_lab_models';
import {TableColumn} from '../services/mtt_models';
import {Notifier} from '../services/notifier';
import {StorageService} from '../services/storage_service';
import {TfcClient} from '../services/tfc_client';
import {DeviceRecoveryStateRequest, FilterHintList, FilterHintType, NoteList, RecoveryState, TestHarness} from '../services/tfc_models';
import {UserService} from '../services/user_service';
import {FilterBarUtility} from '../shared/filterbar_util';
import {OverflowListType} from '../shared/overflow_list';
import {DEFAULT_PAGE_SIZE, Paginator} from '../shared/paginator';
import {TableRowsSelectManager} from '../shared/table_rows_select';
import {areArraysEqual, assertRequiredInput, buildApiErrorMessage, getFilterDefaultSingleValue, removeFirst} from '../shared/util';

/** Displaying a list of devices. */
@Component({
  selector: 'device-list',
  styleUrls: ['device_list.css'],
  templateUrl: './device_list.ng.html',
})
export class DeviceList implements OnChanges, OnDestroy, OnInit {
  /** Periodically updates the device list. */
  @Input() autoUpdate = false;
  /** Enables the selection column. */
  @Input() selectEnabled = true;
  /** Enables the notes button and action column. */
  @Input() notesEnabled = true;
  /** Validates the initially selected devices. */
  @Input() validationEnabled = false;
  @Input() initialSelection: string[] = [];
  @Output() readonly selectedSerialsChange = new EventEmitter<string[]>();

  selectedSerials: string[] = [];
  isLoading = false;
  private readonly destroy = new ReplaySubject<void>();
  dataSource: LabDeviceInfo[] = [];
  readonly overflowListType = OverflowListType;
  readonly allOptionsValue = ALL_OPTIONS_VALUE;

  @ViewChild('table', {static: true, read: ElementRef}) table!: ElementRef;
  @ViewChild(MatTable, {static: true}) matTable!: MatTable<{}>;
  @ViewChild(TableRowsSelectManager, {static: true})
  tableRowsSelectManager!: TableRowsSelectManager;
  isTableScrolled = false;
  displayColumns: string[] = [];
  columns: TableColumn[] = [
    {fieldName: 'select', displayName: 'select', removable: false, show: true},
    {
      fieldName: 'device_serial',
      displayName: 'Device Serial',
      removable: false,
      show: true
    },
    {fieldName: 'sponge', displayName: 'Sponge', removable: true, show: true},
    {
      fieldName: 'hostname',
      displayName: 'Hostname',
      removable: true,
      show: true
    },
    {
      fieldName: 'host_group',
      displayName: 'Host Group',
      removable: true,
      show: true
    },
    {fieldName: 'pools', displayName: 'Pools', removable: true, show: true},
    {fieldName: 'state', displayName: 'State', removable: true, show: true},
    {fieldName: 'product', displayName: 'Product', removable: true, show: true},
    {fieldName: 'variant', displayName: 'Variant', removable: true, show: true},
    {
      fieldName: 'run_target',
      displayName: 'Run Targets',
      removable: true,
      show: true
    },
    {
      fieldName: 'build_id',
      displayName: 'Build Id',
      removable: true,
      show: true
    },
    {
      fieldName: 'sim_state',
      displayName: 'SIM State',
      removable: true,
      show: true
    },
    {
      fieldName: 'battery_level',
      displayName: 'Battery',
      removable: true,
      show: true
    },
    {
      fieldName: 'testHarness',
      displayName: 'Test Harness',
      removable: true,
      show: true
    },
    {
      fieldName: 'notesUpdateTime',
      displayName: 'Notes Update Time',
      removable: true,
      show: true
    },
    {
      fieldName: 'offline_reason',
      displayName: 'Offline Reason',
      removable: true,
      show: true
    },
    {
      fieldName: 'recovery_action',
      displayName: 'Recovery Action',
      removable: true,
      show: true
    },
    {fieldName: 'note', displayName: 'Note', removable: true, show: true},
  ];
  readonly columnDisplayStorageKey = 'DEVICE_LIST_COLUMN_DISPLAY';

  @ViewChild(Paginator, {static: true}) paginator!: Paginator;
  // Pagination tokens used to go backwards or forwards
  prevPageToken?: string;
  nextPageToken?: string;
  readonly deviceListPageSize = 'deviceListPageSize';
  readonly deviceListPageToken = 'deviceListPageToken';
  readonly allSize = 10000;
  readonly pageSizeOptions = [10, 50, 100, 500, 1000, this.allSize];

  labs: string[] = [];
  selectedLab = '';

  @ViewChild('valueInput', {static: true}) valueInput!: ElementRef;
  @ViewChild('valueInput', {static: true, read: MatAutocompleteTrigger})
  matAutocompleteTrigger!: MatAutocompleteTrigger;
  @ViewChild('auto', {static: true}) matAutocomplete!: MatAutocomplete;
  valueControl = new UntypedFormControl({value: ''});
  formGroup = new UntypedFormGroup({
    'valueControl': this.valueControl,
  });

  filterBarUtility!: FilterBarUtility;
  readonly searchableColumns = new Map<string, FilterHintType>([
    ['Host Group', FilterHintType.HOST_GROUP],
    ['Hostname', FilterHintType.HOST],
    ['Pool', FilterHintType.POOL],
    ['State', FilterHintType.DEVICE_STATE],
    ['Test Harness', FilterHintType.TEST_HARNESS],
    ['Run Target', FilterHintType.RUN_TARGET],
  ]);
  readonly extraInfoDisplay = 'Extra Info';
  readonly extraInfoParamName = 'extraInfo';
  readonly labParamName = 'lab';
  readonly deviceSerialDisplay = 'Device Serial';
  readonly deviceSerialParamName = 'deviceSerial';
  readonly back = 'Back';

  readonly searchCriteriaStorageKey = 'DeviceListSearchCriteria';

  readonly recoveryState = RecoveryState;
  readonly testHarness = TestHarness;
  logUrl = '';
  sessionStorageKey = '';
  deviceHostMap: Array < [string, string] >= [];
  urlParams: ParamMap = convertToParamMap({});
  readonly atsHiddenColumns = [
    'sponge',
    'host_group',
    'pools',
    'testHarness',
    'notesUpdateTime',
    'offline_reason',
    'recovery_action',
    'note',
    'run_target',
  ];
  private readonly urlQueryParamObservable: Observable<ParamMap> =
      this.route.queryParamMap.pipe(take(1));
  private readonly autoUpdateInterval = 30_000;

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

  /**
   * Whether the matAutocomplete is displaying root options or not. It's not
   * used for the scenario that users directly enter the criteria string into
   * the filterbar-input without being interactive with the matAutocomplete.
   */
  get isRoot(): boolean {
    return this.filterBarUtility.isRoot();
  }

  get hasFilter(): boolean {
    return this.filterBarUtility.hasFilter();
  }

  get deviceSerials() {
    return this.dataSource.map(info => info.device_serial);
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
      readonly userService: UserService,
      @Inject(APP_DATA) readonly appData: AppData,
  ) {
    if (!this.appData.isAtsLabInstance) {
      // Hide unnecessary fields in the ATS instance.
      this.columns = this.columns.filter(
          x => !this.atsHiddenColumns.includes(x.fieldName));
      // Hide notes button and action column in ATS instance.
      this.notesEnabled = false;
      this.autoUpdate = true;
    } else {
      // ATS lab
      this.logUrl = appData.logUrl || '';
    }
  }

  ngOnInit() {
    assertRequiredInput(this.paginator, 'paginator', 'device-list');
    assertRequiredInput(this.table, 'table', 'device-list');
    assertRequiredInput(this.valueInput, 'valueInput', 'device-list');
    assertRequiredInput(
        this.matAutocompleteTrigger, 'matAutocompleteTrigger', 'device-list');
    assertRequiredInput(this.matAutocomplete, 'matAutocomplete', 'device-list');
    assertRequiredInput(this.matTable, 'matTable', 'device-list');
    assertRequiredInput(
        this.tableRowsSelectManager, 'tableRowsSelectManager', 'device-list');

    if (this.notesEnabled) {
      this.columns.push({
        fieldName: 'actions',
        displayName: 'Actions',
        removable: true,
        show: true
      });
    }
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
    this.tableRowsSelectManager.selectSelection([...this.initialSelection]);
    if (this.autoUpdate) {
      timer(0, this.autoUpdateInterval)
          .pipe(takeUntil(this.destroy))
          .subscribe(() => {
            this.load(0, true);
          });
    }
  }

  ngOnChanges(changes: SimpleChanges) {
    // Only process changes if initialSelection (input selection set) differs
    // from selectedSerials (internal selection set). This indicates that the
    // selection was modified outside of this component.
    if (changes['initialSelection'] &&
        !areArraysEqual(this.initialSelection, this.selectedSerials)) {
      this.tableRowsSelectManager.clearSelection();
      this.tableRowsSelectManager.selectSelection(this.initialSelection);
      if (this.validationEnabled) {
        this.validateSelection();
      }
    }
    // Validate selection if validation becomes enabled.
    if (changes['validationEnabled'] &&
        !changes['validationEnabled'].isFirstChange() &&
        this.validationEnabled) {
      this.validateSelection();
    }
  }

  /** Validate the selected devices by querying the server for them. */
  private validateSelection() {
    const initialSerials = this.selectedSerials.slice();
    if (!initialSerials.length) {
      return;
    }
    const query: DeviceSearchCriteria = {
      deviceSerial: initialSerials,
      includeOfflineDevices: this.appData.isAtsLabInstance ?? true,
    };
    this.tfcClient.queryDeviceInfos(query, initialSerials.length)
        .pipe(takeUntil(this.destroy))
        .subscribe(
            response => {
              // Unselect devices that were not found by the server. Ignore
              // devices selected during validation by iterating over a copy of
              // the initial selection.
              let selectionChanged = false;
              const actualSerials =
                  (response.deviceInfos || []).map(di => di.device_serial);
              for (const serial of initialSerials) {
                if (!actualSerials.includes(serial)) {
                  selectionChanged = removeFirst(this.selectedSerials, serial);
                }
              }
              if (selectionChanged) {
                this.tableRowsSelectManager.clearSelection();
                this.tableRowsSelectManager.selectSelection(
                    this.selectedSerials);
              }
            },
            error => {
              console.warn('Failed to validate selected devices:', error);
            });
  }

  setFilterBarParameters() {
    const filterBarColumns = [
      'Host Group',
      'Hostname',
      'Pool',
      'State',
      'Test Harness',
      'Run Target',
      this.deviceSerialDisplay,
      this.extraInfoDisplay,
    ];

    // The mapping of display(column) name and parameter name.
    const searchCriteriaMapping = new Map<string, string>([
      ['Host Group', 'hostGroups'],
      ['Hostname', 'hostnames'],
      ['Lab', 'lab'],
      ['Pool', 'pools'],
      ['Test Harness', 'testHarness'],
      ['Run Target', 'runTargets'],
      ['State', 'deviceStates'],
      [this.deviceSerialDisplay, this.deviceSerialParamName],
      [this.extraInfoDisplay, this.extraInfoParamName],
    ]);

    this.filterBarUtility = new FilterBarUtility(
        [], filterBarColumns, searchCriteriaMapping, 30, 'type', 1,
        [this.deviceSerialDisplay, this.extraInfoDisplay]);
  }

  /** Initializes all criteria for the filterbar then bind table. */
  initFilterBarThenLoad() {
    this.filterBarUtility.initFilterbarRoots();
    forkJoin([
      this.getLabObservable(),
      this.getFilterHintObservable(FilterHintType.HOST),
      this.getFilterHintObservable(FilterHintType.HOST_GROUP),
      this.getFilterHintObservable(FilterHintType.TEST_HARNESS),
      this.getFilterHintObservable(FilterHintType.POOL),
      this.getFilterHintObservable(FilterHintType.DEVICE_STATE),
      this.getFilterHintObservable(FilterHintType.RUN_TARGET),
    ])
        .pipe(
            retryWhen((errors) => errors.pipe(delay(500), take(3))),
            mergeMap(() => this.urlQueryParamObservable),
            map((params: ParamMap) => {
              this.urlParams = params;
              const urlParam = this.urlParams.get(this.labParamName) ?? '';
              const storedParam = this.loadSelectedLabFromLocalStorage();
              this.selectedLab =
                  getFilterDefaultSingleValue(this.labs, urlParam, storedParam);
            }),
            concatMap(() => this.updatePaginatorParamsAndLoad()),
            mergeMap((response) => {
              this.afterDataloaded(response);
              return this.tfcClient.batchGetDevicesLatestNotes(
                  this.dataSource.map(x => x.device_serial));
            }),
            takeUntil(this.destroy),
            )
        .subscribe(
            (result) => {
              this.setDeviceNotes(result);
            },
            () => {
              this.notifier.showError('Failed to load device list');
            });
  }

  getLabObservable(): Observable<void> {
    return this.tfcClient.getFilterHintList(FilterHintType.LAB)
        .pipe(
            map((result) => {
              this.labs = result.filter_hints?.map((item) => item.value) ?? [];
            }),
        );
  }

  getFilterHintObservable(filterHintType: FilterHintType): Observable<null> {
    // Using localStorage for cache.
    const items = window.localStorage.getItem(String(filterHintType));
    if (items) {
      const result = JSON.parse(items) as FilterOption[];
      this.filterBarUtility.appendFilterOptions(result);
    }
    // Always get from api again to sync the items.
    return this.tfcClient.getFilterHintList(filterHintType)
        .pipe(
            map((result) => this.convertToFilterOptions(
                    result, String(filterHintType))),
            mergeMap((result) => {
              const columnName = this.getColumnName(filterHintType);
              this.filterBarUtility.updateFilterOptions(result, columnName);
              window.localStorage.setItem(
                  String(filterHintType), JSON.stringify(result));
              return observableOf(null);
            }),
            retryWhen((errors) => errors.pipe(delay(500), take(3))),
            takeUntil(this.destroy),
        );
  }

  updatePaginatorParamsAndLoad(): Observable<LabDeviceInfosResponse> {
    const pageToken = this.urlParams.get(this.deviceListPageToken) || '';
    const sizeString =
        this.urlParams.get(this.deviceListPageSize) || DEFAULT_PAGE_SIZE;
    const sizeNumber = Number(sizeString);
    const pageSize =
        !isNaN(sizeNumber) && this.pageSizeOptions.includes(sizeNumber) ?
        sizeNumber :
        DEFAULT_PAGE_SIZE;
    this.prevPageToken = undefined;
    this.nextPageToken = pageToken;
    this.paginator.pageSize = pageSize;
    this.paginator.showPageIndex = true;
    const disabledLoadFromLocalStorage = this.hasQueryStringParams();
    for (const type of this.searchableColumns.values()) {
      this.setFilterHintSelectedValues(type, disabledLoadFromLocalStorage);
    }
    this.loadNonFilterHintTypeCriteria();
    this.renderSelectedOptions();
    // Try load from sessionStorage then from api.
    this.setSessionStorageKey();
    const searchResult = window.sessionStorage.getItem(this.sessionStorageKey);
    if (searchResult) {
      const data = JSON.parse(searchResult) as LabDeviceInfosResponse;
      return observableOf(data);
    } else {
      this.isLoading = true;
      return this.tfcClient
          .queryDeviceInfos(
              this.getSearchCriteria(), this.paginator.pageSize, pageToken)
          .pipe(takeUntil(this.destroy));
    }
  }

  hasQueryStringParams(): boolean {
    return this.urlParams.keys.length > 0;
  }

  /** Loads values from queryString or localStorage then set selected. */
  setFilterHintSelectedValues(
      filterHintType: FilterHintType, disabledLoadFromLocalStorage: boolean) {
    const columnName = this.getColumnName(filterHintType);
    const paraName = this.filterBarUtility.getParameterName(columnName);
    let values = this.urlParams.getAll(paraName) || [];
    if ((!values || values.length === 0) && !disabledLoadFromLocalStorage) {
      values = this.getSearchCriteriaFromLocalStorage(filterHintType);
    }
    this.filterBarUtility.setFilterOptionsSelected(columnName, values);
  }

  ngOnDestroy() {
    this.destroy.next();
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
    const sessionStorageResult =
        window.sessionStorage.getItem(this.sessionStorageKey);
    this.patchQueryParams();
    if (sessionStorageResult && !forceRefresh) {
      this.afterDataloaded(
          JSON.parse(sessionStorageResult) as LabDeviceInfosResponse, true);
    } else {
      this.tfcClient
          .queryDeviceInfos(
              searchCriteria, this.getPageSize(), pageToken, previous)
          .pipe(
              takeUntil(this.destroy),
              mergeMap((result) => {
                this.afterDataloaded(result);
                return this.tfcClient.batchGetDevicesLatestNotes(
                    this.dataSource.map(x => x.device_serial));
              }),
              )
          .subscribe(
              (result) => {
                this.setDeviceNotes(result);
              },
              () => {
                this.notifier.showError('Failed to load device list');
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

  /** Loads the latest updated notes after the add notes dialog is closed. */
  loadDeviceNotes(deviceSerials: string[]) {
    this.tfcClient.batchGetDevicesLatestNotes(deviceSerials)
        .pipe(takeUntil(this.destroy))
        .subscribe(
            (result) => {
              this.setDeviceNotes(result);
            },
            () => {
              this.notifier.showError(
                  'Failed to load latest notes for devices');
            });
  }

  setDeviceNotes(noteList: NoteList) {
    if (noteList && noteList.notes) {
      for (const note of noteList.notes) {
        const deviceInfo = this.dataSource.find(
            device => device.device_serial === note.device_serial);
        if (deviceInfo) {
          deviceInfo.note = note;
        }
      }
      const result: LabDeviceInfosResponse = {
        deviceInfos: this.dataSource,
        nextCursor: this.nextPageToken,
        prevCursor: this.prevPageToken,
        more: this.nextPageToken !== '',
      };
      if (this.sessionStorageKey && this.appData.isAtsLabInstance) {
        window.sessionStorage.setItem(
            this.sessionStorageKey, JSON.stringify(result));
      }
    }
  }

  setSessionStorageKey() {
    const searchCriteria = this.getSearchCriteria();
    this.sessionStorageKey = `${JSON.stringify(searchCriteria)}-${
        String(this.getPageSize())}-${String(this.paginator.pageIndex)}`;
  }

  getPageSize(): number {
    return this.paginator.pageSize;
  }

  /** Handles the api returns data and switch status. */
  afterDataloaded(
      result: LabDeviceInfosResponse, isFromSessionStorage = false) {
    this.dataSource = result.deviceInfos || [];
    this.prevPageToken = result.prevCursor;
    this.nextPageToken = result.nextCursor;
    this.isLoading = false;
    this.filterBarUtility.filterChanged = false;
    this.refreshPaginator();
    this.tableRowsSelectManager.rowIdFieldAllValues = this.deviceSerials;
    this.tableRowsSelectManager.clearSelection();
    this.tableRowsSelectManager.selectSelection(this.selectedSerials);
    this.tableRowsSelectManager.resetPrevClickedRowIndex();
    this.deviceHostMap = this.dataSource.map(
        info => [info.device_serial || '', info.hostname || '']);
    this.liveAnnouncer.announce('Device list loaded', 'assertive');
    if (!isFromSessionStorage) {
      window.sessionStorage.setItem(
          this.sessionStorageKey, JSON.stringify(result));
    }
  }

  resetSearchSteps() {
    this.filterBarUtility.resetSearchSteps();
  }

  getSelectedOptions(type: FilterHintType): string[]|undefined {
    const columnName = this.getColumnName(String(type));
    const selectedOptions =
        this.filterBarUtility.getFilterOptions(columnName, true)
            .map(x => x.value);
    return selectedOptions.length ? selectedOptions : undefined;
  }

  getSearchCriteria(): DeviceSearchCriteria {
    const searchCriteria: DeviceSearchCriteria = {};
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
    if (this.getSelectedOptions(FilterHintType.POOL)) {
      searchCriteria.pools = this.getSelectedOptions(FilterHintType.POOL);
    }
    if (this.getSelectedOptions(FilterHintType.DEVICE_STATE)) {
      searchCriteria.deviceStates =
          this.getSelectedOptions(FilterHintType.DEVICE_STATE);
    }
    if (this.getSelectedOptions(FilterHintType.RUN_TARGET)) {
      searchCriteria.runTargets =
          this.getSelectedOptions(FilterHintType.RUN_TARGET);
    }
    const deviceSerial =
        this.filterBarUtility.getInputFilterOption(this.deviceSerialDisplay);
    if (deviceSerial) {
      searchCriteria.deviceSerial = [deviceSerial];
    }
    const extraInfo =
        this.filterBarUtility.getInputFilterOption(this.extraInfoDisplay);
    if (extraInfo) {
      searchCriteria.extraInfo = [extraInfo];
    }
    searchCriteria.includeOfflineDevices =
        this.appData.isAtsLabInstance ?? true;
    return searchCriteria;
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

  /** When device state is GONE, user can remove(hide) the device. */
  removeDevice(deviceSerial: string, hostname: string) {
    this.notifier.confirm('', REMOVE_DEVICE_MESSAGE, 'Remove device', 'Cancel')
        .pipe(
            switchMap((result) => {
              if (!result) return observableOf(false);
              return this.tfcClient.removeDevice(deviceSerial, hostname)
                  .pipe(
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
                  this.dataSource.filter(x => x.device_serial !== deviceSerial);
              this.matTable.renderRows();
              this.notifier.showMessage(`Device '${deviceSerial}' removed`);
              this.load(0, true);
            },
            (error) => {
              this.notifier.showError(
                  `Failed to remove device ${deviceSerial}`,
                  buildApiErrorMessage(error));
            });
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
      this.filterBarUtility.displayLeafFilterOptions(option.value);
      this.renderSelectedOptions(option.value);
      setTimeout(() => {
        this.matAutocomplete._setScrollTop(0);
      }, 0);
    } else {
      // Leaf
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

  /** Displays the selected filters. */
  renderSelectedOptions(columnName: string = '') {
    let selectedOptionsString = this.filterBarUtility.getSelectedOptionString();
    if (columnName &&
        this.filterBarUtility.getFilterOptions(columnName, true).length === 0) {
      selectedOptionsString = `${selectedOptionsString} ${columnName}:`;
    }
    this.setSelectedOptionsString(selectedOptionsString);
  }

  getSearchCriteriaFromLocalStorage(type: FilterHintType): string[] {
    const columnName = this.getColumnName(type);
    return this.getSearchCriteriaFromLocalStorageByProperty(
        this.filterBarUtility.getParameterName(columnName));
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

  /** Converts api data to filterOptions. */
  convertToFilterOptions(
      filterHintList: FilterHintList, filterHintType: string): FilterOption[] {
    const filterHints = filterHintList.filter_hints || [];
    const columnName = this.getColumnName(filterHintType);
    return this.createFilterOptions(
        filterHints.filter(x => x && x.value).map(x => x.value), columnName,
        true, true);
  }

  /** Creates filter options. */
  createFilterOptions(
      values: string[], columnName: string, hidden: boolean = false,
      showCheckbox: boolean = false): FilterOption[] {
    const options: FilterOption[] = [];
    for (const value of values) {
      options.push(
          {value, selected: false, type: columnName, hidden, showCheckbox});
    }
    return options;
  }

  /** Gets search criteria display name. */
  getColumnName(filterHintType: string): string {
    for (const [key, value] of this.searchableColumns.entries()) {
      if (filterHintType === value) return key;
    }
    return '';
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
    const value = this.matAutocompleteTrigger.activeOption?.value;
    this.dispatchHandler(value, event);
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
      // Type a column name then press enter on the input. e.g. pool+Enter. The
      // menu should display the options belong to the 'Pool' and keep the menu
      // opening.
      if (this.filterBarUtility.isRootColumn(this.inputValue) ||
          this.filterBarUtility.isEditingInputColumn()) {
        this.dispatchHandler(this.lookupColumnValue, event);
      } else if (
          this.filterBarUtility.searchCriteriaSnapshot !== this.inputValue) {
        this.parseInputValue(this.inputValue);
        this.matAutocompleteTrigger.closePanel();
        this.load();
        this.renderSelectedOptions();
        this.filterBarUtility.searchCriteriaSnapshot = this.inputValue;
      }
    }
    this.startDeviceFilterBarHats();
  }

  dispatchHandler(selectedValue: string, event: KeyboardEvent) {
    if (selectedValue === this.back) {
      this.backToRoot(event);
      return;
    } else if (selectedValue === this.allOptionsValue) {
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
      this.addInputOption(selectedValue, this.filterBarUtility.selectedColumn);
      return;
    }
    const filterOption = this.getFilterOption(type, selectedValue);
    this.toggleSelection(event, filterOption);
  }

  /** Finds the FilterOption or create a new one. */
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

  /**
   * The searching value of Device serial and extrInfo comes from user input.
   */
  addInputOption(value: string, columnName: string) {
    if (columnName === this.deviceSerialDisplay) {
      this.filterBarUtility.addNewFilterOption(value, this.deviceSerialDisplay);
    } else if (columnName === this.extraInfoDisplay) {
      if (value.indexOf(':') > -1 || value.indexOf('=') > -1) {
        this.filterBarUtility.addNewFilterOption(value, this.extraInfoDisplay);
      } else {
        this.notifier.showError('Incorrect format. The format is "key:value"');
      }
    }
  }

  getQueryParamsFromOptions(): DeviceQueryParams {
    const queryParams: DeviceQueryParams = {};
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
    if (this.getSelectedOptions(FilterHintType.POOL)) {
      queryParams.pools = this.getSelectedOptions(FilterHintType.POOL);
    }
    if (this.getSelectedOptions(FilterHintType.DEVICE_STATE)) {
      queryParams.deviceStates =
          this.getSelectedOptions(FilterHintType.DEVICE_STATE);
    }
    if (this.getSelectedOptions(FilterHintType.RUN_TARGET)) {
      queryParams.runTargets =
          this.getSelectedOptions(FilterHintType.RUN_TARGET);
    }
    if (this.getSelectedOptions(FilterHintType.RUN_TARGET)) {
      queryParams.runTargets =
          this.getSelectedOptions(FilterHintType.RUN_TARGET);
    }
    if (this.prevPageToken) {
      queryParams.deviceListPageToken = this.prevPageToken;
    }
    if (this.paginator.pageSize !== DEFAULT_PAGE_SIZE) {
      queryParams.deviceListPageSize = this.paginator.pageSize;
    }
    queryParams.includeOfflineDevices = this.appData.isAtsLabInstance ?? true;
    queryParams.extraInfo =
        [this.filterBarUtility.getInputFilterOption(this.extraInfoDisplay)];

    return queryParams;
  }

  saveSearchCriteriaToLocalStorage() {
    window.localStorage.setItem(
        this.searchCriteriaStorageKey,
        JSON.stringify(this.getSearchCriteria()));
  }

  loadSearchCriteriaFromLocalStorage(): DeviceSearchCriteria {
    const criteria = window.localStorage.getItem(this.searchCriteriaStorageKey);
    return criteria ? JSON.parse(criteria) as DeviceSearchCriteria : {
      lab: '',
      hostnames: [],
      hostGroups: [],
      testHarness: [],
      pools: [],
      deviceStates: [],
      runTargets: [],
      deviceSerial: [],
      extraInfo: [],
      includeOfflineDevices: this.appData.isAtsLabInstance ?? true,
    };
  }

  /** Loads extraInifo and device serial from query string and localstorage. */
  loadNonFilterHintTypeCriteria() {
    let extraInfo = this.urlParams.get(this.extraInfoParamName);
    if (!extraInfo) {
      extraInfo = this.getSearchCriteriaFromLocalStorageByProperty(
          this.extraInfoParamName)[0];
    }
    if (extraInfo) this.addInputOption(extraInfo, this.extraInfoDisplay);

    let deviceSerial = this.urlParams.get(this.deviceSerialParamName);
    if (!deviceSerial) {
      deviceSerial = this.getSearchCriteriaFromLocalStorageByProperty(
          this.deviceSerialParamName)[0];
    }
    if (deviceSerial) {
      this.addInputOption(deviceSerial, this.deviceSerialDisplay);
    }
  }

  saveSelectedLabToLocalStorage() {
    window.localStorage.setItem(LAB_STORAGE_KEY, this.selectedLab);
  }

  loadSelectedLabFromLocalStorage(): string {
    return window.localStorage.getItem(LAB_STORAGE_KEY) || '';
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

  /** Naviagte to device details page. */
  openDeviceDetails(deviceSerial: string) {
    this.storageService.deviceList = this.deviceSerials;
    const url = this.getDeviceDetailsUrl(deviceSerial);
    this.router.navigateByUrl(url);
  }

  getDeviceDetailsUrl(deviceSerial: string): string {
    const url = this.router.serializeUrl(
        this.router.createUrlTree(['/devices', deviceSerial]));
    return url;
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
          this.addInputOption(inputOptions[0], columnName);
        } else if (inputOptions.length > 1) {
          this.notifier.showWarning(
              `'${columnName}' only supports single value`);
        } else {
          this.filterBarUtility.clearInputOption(columnName);
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

  startBatchAddDevicesNotesHats() {
    this.feedbackService.startSurvey(SurveyTrigger.BATCH_ADD_DEVICES_NOTES);
  }

  startViewDevicesColumnsHats() {
    this.feedbackService.startSurvey(SurveyTrigger.VIEW_DEVICES_COLUMNS);
  }

  startDeviceFilterBarHats() {
    this.feedbackService.startSurvey(SurveyTrigger.DEVICE_FILTER_BAR);
  }

  toggleDeviceFixedState(device: LabDeviceInfo, event: MouseEvent) {
    event.stopPropagation();

    const currentState = device.recovery_state;
    const fixedMsg = `The device's recovery state has been marked as FIXED`;
    const undoMsg = `The device's recovery state marked back as UNKNOWN.`;
    const errMsg = `Failed to mark the device's recovery state as FIXED`;
    const msg = currentState === RecoveryState.FIXED ? undoMsg : fixedMsg;

    const nextState = currentState === RecoveryState.FIXED ?
        RecoveryState.UNKNOWN :
        RecoveryState.FIXED;

    const deviceRecoveryStateRequests = [{
      hostname: device.hostname,
      device_serial: device.device_serial,
      recovery_state: nextState,
    } as DeviceRecoveryStateRequest];

    this.tfcClient.batchSetDevicesRecoveryStates(deviceRecoveryStateRequests)
        .pipe(takeUntil(this.destroy))
        .subscribe(
            () => {
              device.recovery_state = nextState;
              this.notifier.showMessage(msg);
              this.liveAnnouncer.announce(msg, 'assertive');
            },
            () => {
              this.notifier.showError(errMsg);
            });
  }

  getLogUrl(device: LabDeviceInfo): string {
    return this.logUrl.replace(HOSTNAME, device.hostname || '')
        .replace(DEVICE_SERIAL, device.device_serial);
  }

  storeDeviceSerialsInLocalStorage() {
    this.storageService.saveDeviceListInLocalStorage(this.deviceSerials);
  }

  updateSelectedDeviceSerials(selectedSerials: string[]) {
    this.selectedSerials = selectedSerials;
    this.selectedSerialsChange.emit(this.selectedSerials);
  }
}
