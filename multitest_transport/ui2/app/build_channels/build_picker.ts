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
import {Component, EventEmitter, Inject, OnDestroy, OnInit, Output, ViewChild} from '@angular/core';
import {MAT_DIALOG_DATA, MatDialogRef} from '@angular/material/dialog';
import {MatTabChangeEvent} from '@angular/material/tabs';
import {MatTable} from '@angular/material/table';
import {ReplaySubject, Subject, Subscription} from 'rxjs';
import {debounceTime, delay, finalize, first, takeUntil} from 'rxjs/operators';

import {joinPath} from '../services/file_service';
import {MttClient} from '../services/mtt_client';
import {AuthorizationMethod, BuildChannel, BuildItem, BuildItemPathType, isBuildChannelAvailable} from '../services/mtt_models';
import {Notifier} from '../services/notifier';
import {InfiniteScrollLoadEvent} from '../shared/infinite_scroll';
import {buildApiErrorMessage, isFnmatchPattern} from '../shared/util';

/** Build provider names. */
const LOCAL_FILE_PROVIDER = 'Local File Store';
const GCS_PROVIDER = 'Google Cloud Storage';

/**
 * Actions the build picker should allow
 *
 * VIEW: View each build channel (no url), can upload files to local file store
 * SELECT: Select a file from the available build channels to return
 */
export enum BuildPickerMode {
  VIEW,
  SELECT,
}

/**
 * Data passed when opening the build picker.
 * @param buildChannels: a list of build channels
 * @param resourceUrl: optional initial resource URL
 */
export interface BuildPickerData {
  buildChannels: BuildChannel[];
  mode: BuildPickerMode;
  resourceUrl?: string;
}

/**
 * A state object for BuildPicker
 * @param searchBarUrlValue: an url which can be a path or full url
 * @param searchBarFilenameValue: a filename which can be glob pattern
 */
export interface BuildPickerTabState {
  searchBarUrlValue: string;
  searchBarFilenameValue: string;
}

/**
 * Build Picker
 * This component is used to select resource urls from build channels
 */
@Component({
  selector: 'build-picker',
  styleUrls: ['build_picker.css'],
  templateUrl: './build_picker.ng.html',
})
export class BuildPicker implements OnInit, OnDestroy {
  readonly AuthorizationMethod = AuthorizationMethod;
  readonly isBuildChannelAvailable = isBuildChannelAvailable;
  readonly isFnmatchPattern = isFnmatchPattern;
  readonly BuildItemPathType = BuildItemPathType;

  private readonly destroy = new ReplaySubject<void>();

  /** Update build channels in parent after authorization. */
  @Output() readonly buildChannelsChange = new EventEmitter<BuildChannel[]>();

  readonly BuildPickerMode = BuildPickerMode;
  mode = BuildPickerMode.SELECT;

  /** Tab related variable */
  buildChannels: BuildChannel[];
  selectedTabIndex = 0;
  selectedBuildChannel?: BuildChannel;
  /** Number of static tabs (which do not correspond to a build channel). */
  numStaticTabs = 2;

  /** Table related variable */
  buildItems: BuildItem[] = [];
  buildItemsSubscription?: Subscription;
  nextPageToken: string = '';
  isLoadingBuildItems = false;
  columnsToDisplay = ['name', 'timestamp', 'size', 'navIcon'];
  @ViewChild(MatTable, {static: false}) table!: MatTable<{}>;
  selection = new SelectionModel<BuildItem>(
      /*allow multi select*/ false, []);

  /** Search bar related variable */
  searchBarUrlValue = '';
  searchBarFilenameValue = '';

  /** Track build picker state when switch between tabs */
  private readonly buildPickerTabStateMap:
      {[key: number]: BuildPickerTabState} = {};

  private readonly searchUpdated = new Subject<string>();

  ngOnDestroy() {
    this.destroy.next();
  }

  constructor(
      private readonly dialogRef: MatDialogRef<BuildPicker>,
      @Inject(MAT_DIALOG_DATA) data: BuildPickerData,
      private readonly liveAnnouncer: LiveAnnouncer,
      private readonly mttClient: MttClient,
      private readonly notifier: Notifier) {
    // Initialize the build picker
    // TODO: remove local file provider
    this.buildChannels =
        data.buildChannels.filter(c => c.provider_name !== LOCAL_FILE_PROVIDER);
    this.mode = data.mode;
    this.decodeResourceUrl(data.resourceUrl);

    if (this.mode === BuildPickerMode.VIEW) {
      this.numStaticTabs = 1;  // Local File Store only
    } else {
      this.numStaticTabs = 2;  // Url and Local File Store
    }
    // When search updated, reload the current build list
    this.searchUpdated.asObservable()
        .pipe(debounceTime(200), takeUntil(this.destroy))
        .subscribe(
            () => {
              this.loadBuildList();
            },
            error => {
              // TODO: Refine error handling in build picker
              console.error(error);
            });
  }

  ngOnInit() {
    this.loadBuildList();
  }

  /** Close the dialog and return the selected resource URL. */
  selectAndClose() {
    this.dialogRef.close(this.encodeResourceUrl());
  }

  /** Parse a resource URL to initialize search bar parameters. */
  private decodeResourceUrl(url?: string): void {
    if (!url) {
      return;  // No resource URL provided, use default parameters
    }

    const match = url.match(/^mtt:\/\/\/([^\/]+)\/((.*)\/(.*)|(.*))$/i);
    if (!match) {
      // Not a build channel URL
      this.selectedTabIndex = url.startsWith('file://') ? 1 : 0;
      this.searchBarUrlValue = url;
      return;
    }
    // Find relevant build channel
    const channelId = match[1];
    const channelIndex = this.buildChannels.findIndex(c => c.id === channelId);
    this.selectedBuildChannel = this.buildChannels[channelIndex];
    this.selectedTabIndex = channelIndex + this.numStaticTabs;
    // Set search bar parameters
    if (this.isUrlBuildChannel()) {
      this.searchBarUrlValue = decodeURIComponent(match[2]) || '';
    } else {
      this.searchBarUrlValue = match[3] || '';
      this.searchBarFilenameValue = decodeURIComponent(match[4] || match[5]);
    }
  }

  /** Encode the search bar parameters into a resource URL. */
  private encodeResourceUrl(): string {
    let url = this.searchBarUrlValue.trim();
    if (this.isUrlBuildChannel()) {
      url = encodeURIComponent(url);
    }
    if (this.selectedBuildChannel) {
      url = `mtt:///${this.selectedBuildChannel.id}/${url}`;
    }
    if (this.searchBarFilenameValue) {
      url =
          joinPath(url, encodeURIComponent(this.searchBarFilenameValue.trim()));
    }
    return url;
  }

  private loadBuildChannels() {
    this.mttClient.getBuildChannels().pipe(first()).subscribe(
        result => {
          this.buildChannels = result.build_channels || [];
          this.buildChannelsChange.emit(this.buildChannels);
          this.selectedBuildChannel =
              this.buildChannels[this.selectedTabIndex - this.numStaticTabs];
          this.loadBuildList();
        },
        error => {
          this.notifier.showError(
              'Failed to load build channels', buildApiErrorMessage(error));
        });
  }

  /**
   * Listener for selected tab change event
   * Note: 0th tab is always 'By Url' where user provide the web url
   * The other tabs could include Google Drive, Local file store, and more
   * @param tabEvent A tab change event
   */
  onSelectedTabChange(tabEvent: MatTabChangeEvent) {
    // When switching between tabs, it's possible that one subscription
    // is still loading while the second subscription started. Thus, it's
    // possible that first subscription finishes even later than then
    // second subscription, resulting in conflicting data. Unsubscribe can
    // resolve this issue.
    if (this.buildItemsSubscription) {
      this.isLoadingBuildItems = false;
      this.buildItemsSubscription.unsubscribe();
    }

    // Save the state before tab change
    this.buildPickerTabStateMap[this.selectedTabIndex] = {
      searchBarUrlValue: this.searchBarUrlValue,
      searchBarFilenameValue: this.searchBarFilenameValue
    };
    // Load old state if exist
    this.selectedTabIndex = tabEvent.index;
    const state = this.buildPickerTabStateMap[this.selectedTabIndex];
    if (state) {
      this.searchBarUrlValue = state.searchBarUrlValue || '';
      this.searchBarFilenameValue = state.searchBarFilenameValue || '';
    } else {
      this.searchBarUrlValue = '';
      this.searchBarFilenameValue = '';
    }
    this.nextPageToken = '';
    this.selection.clear();

    this.selectedBuildChannel =
        this.buildChannels[tabEvent.index - this.numStaticTabs];
    this.loadBuildList();
  }

  /**
   * In search bar, when the value changes, fire a searchUpdated event with
   * the updated searchValue
   * @param searchValue
   */
  onSearchBarValueChange(searchValue: string) {
    this.searchUpdated.next(searchValue);
    this.selection.clear();
  }

  /**
   * Load build item list.
   * @param nextPageToken Next page token indicate there's more content left
   * in the page
   */
  loadBuildList(nextPageToken?: string|undefined) {
    // Don't load if buildchannel is not defined
    // Don't load if build item path is url
    // Don't load if the selectedBuildChannel is not available/not authenticated
    // Don't load if it's a glob pattern
    if (!this.selectedBuildChannel || this.isUrlBuildChannel() ||
        !isBuildChannelAvailable(this.selectedBuildChannel) ||
        isFnmatchPattern(this.searchBarUrlValue)) {
      return;
    }
    // Clear builds when nextPageToken is undefined (new path is being loaded)
    if (!nextPageToken) {
      this.buildItems.length = 0;
    }
    // Load build item
    const path = this.searchBarUrlValue;

    if (this.buildItemsSubscription) {
      this.buildItemsSubscription.unsubscribe();
    }
    this.isLoadingBuildItems = true;
    this.liveAnnouncer.announce('Loading', 'polite');
    this.buildItemsSubscription =
        this.mttClient
            .listBuildItems(this.selectedBuildChannel.id, path, nextPageToken)
            .pipe(takeUntil(this.destroy))
            .pipe(finalize(() => {
              this.isLoadingBuildItems = false;
            }))
            .subscribe(
                result => {
                  this.buildItems =
                      this.buildItems.concat(result.build_items || []);
                  this.nextPageToken = result.next_page_token || '';
                  if (this.table) {
                    this.table.renderRows();
                  }
                  this.liveAnnouncer.announce(
                      'Build items loaded', 'assertive');
                },
                error => {
                  this.buildItems.length = 0;
                  if (error.status !== 404) {
                    // Display all errors except not found errors which may just
                    // indicate the user is still typing the filename.
                    // TODO: show errors in the build picker dialog
                    this.notifier.showError(
                        'Failed to load files.', buildApiErrorMessage(error));
                  }
                });
  }

  /**
   * In mat table, on clicking a row (a BuildItem), set selected item
   * to current item
   * @param row BuildItem
   */
  selectFile(row: BuildItem) {
    if (row.is_file) {
      this.selection.select(row);
      this.searchBarFilenameValue = row.name;
    }
  }

  /**
   * In mat table, on double clicking a row (a BuildItem), update breadcrumb
   * and searchbar
   * @param row
   */
  openFolder(row: BuildItem) {
    if (row.is_file) {
      // TODO: [MTT][UI2][Build Picker] Sync with design on double
      // click on a file
      return;
    }
    this.selection.clear();
    this.onBreadCrumbPathChange(row.path);
  }

  /**
   * Triggered when breadcrumb path has changed
   * @param updatedSearchBarValue Current Search Bar Value
   */
  onBreadCrumbPathChange(updatedSearchBarValue: string) {
    this.searchBarUrlValue = updatedSearchBarValue;
    this.searchBarFilenameValue = '';
    this.loadBuildList();
    this.selection.clear();
  }

  /**
   * When scrolling the table, this action will be triggered when more content
   * is needed.
   * @param event An InfiniteScrollLoadEvent event
   */
  onScrollLoad(event: InfiniteScrollLoadEvent) {
    // To avoid double loading, we only load if previous load finished.
    if (!this.isLoadingBuildItems) {
      this.loadBuildList(this.nextPageToken);
    }
    event.completed = Promise.resolve(!!this.nextPageToken);
  }

  /**
   * Authorize Build Channel
   * @param buildChannelId A buildchannel id
   */
  authorize(buildChannelId: string) {
    this.mttClient.authorizeBuildChannel(buildChannelId)
        .pipe(delay(500))  // delay for data to be persisted
        .subscribe(
            () => {
              this.loadBuildChannels();
            },
            error => {
              this.notifier.showError(
                  'Failed to authorize build channel.',
                  buildApiErrorMessage(error));
            });
  }

  /** Authorize a build channel with a service account JSON key. */
  uploadKeyfile(buildChannelId: string, keyFile?: File) {
    if (!keyFile) {
      return;
    }
    this.mttClient
        .authorizeBuildChannelWithServiceAccount(buildChannelId, keyFile)
        .pipe(delay(500))  // Delay for data to be persisted
        .subscribe(
            () => {
              this.loadBuildChannels();
            },
            error => {
              this.notifier.showError(
                  `Failed to authorize build channel '${buildChannelId}'.`,
                  buildApiErrorMessage(error));
            });
  }

  /**
   * Returns true if using a GCS build channel and the search bar is empty
   */
  isMissingGcsBucket(): boolean {
    return !!this.selectedBuildChannel &&
        this.selectedBuildChannel.provider_name === GCS_PROVIDER &&
        !this.searchBarUrlValue;
  }

  /** Returns true if the build item path is url. */
  isUrlBuildChannel(): boolean {
    return !!this.selectedBuildChannel &&
        this.selectedBuildChannel.build_item_path_type ===
        BuildItemPathType.URL;
  }
}
