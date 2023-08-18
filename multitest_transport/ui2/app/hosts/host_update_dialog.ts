/**
 * Copyright 2021 Google LLC
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
import {Component, Inject, OnDestroy, OnInit, ViewChild} from '@angular/core';
import {MAT_DIALOG_DATA, MatDialogRef} from '@angular/material/dialog';
import {MatPaginator} from '@angular/material/paginator';
import {MatRadioChange} from '@angular/material/radio';
import {MatTableDataSource} from '@angular/material/table';
import {MatSort} from '@angular/material/sort';
import {ReplaySubject} from 'rxjs';
import {finalize, takeUntil} from 'rxjs/operators';

import {ALL_OPTIONS_VALUE, ClusterInfo, HostUpdateStateSummary, LabInfo} from '../services/mtt_lab_models';
import {Notifier} from '../services/notifier';
import {TfcClient} from '../services/tfc_client';
import {BatchUpdateHostMetadataRequest, DEFAULT_ALL_COUNT, HostConfig, HostUpdateState, TestHarnessImage} from '../services/tfc_models';
import {assertRequiredInput} from '../shared/util';

/** Default count of test harness images to be selected from each time. */
const DEFAULT_TEST_HARNESS_IMAGE_COUNT = 30;

/**
 * Data to build the host update dialog.
 * 1. The name of selected lab,
 */
export interface HostUpdateDialogData {
  selectedLab: string;
}

/** The enum types to describe lab update mode. */
export enum UpdateMode {
  /** Update the entire lab. */
  LAB = 'LAB',
  /** Update a selected host group. */
  HOST_GROUP = 'HOST_GROUP',
  /** Update selected hosts. */
  HOSTS = 'HOSTS',
}

/** Table element for HostUpdateStateSummary. */
interface HostUpdateStateSummaryElement {
  /** Name of update state. */
  state: string;
  /** Number of hosts in the update state. */
  count: number;
}

/** Table element for HostCountByHarnessVersion. */
interface HostCountByHarnessVersionElement {
  /** The test harness version. */
  version: string;
  /** Number of hosts in the version. */
  count: number;
}

/** Component that manages host updates in a lab. */
@Component({
  selector: 'host-update-dialog',
  styleUrls: ['host_update_dialog.css'],
  templateUrl: './host_update_dialog.ng.html',
})
export class HostUpdateDialog implements OnInit, OnDestroy {
  selectedLab: string;
  selectedHostGroupValue = '';
  selectedHosts: string[] = [];
  selectedTargetVersion = '';
  selectableTargetVersions: string[] = [];
  hostConfigsInLab: HostConfig[] = [];
  candidateHostConfigs: HostConfig[] = [];
  hostGroupNames: string[] = [];
  hostNames: string[] = [];
  labInfoValue: LabInfo|null = null;
  clusterInfoValue: ClusterInfo|null = null;
  selectedMode: UpdateMode = UpdateMode.LAB;
  selectedImage: TestHarnessImage|null = null;
  imageTagPrefix = '';
  testHarnessImages: TestHarnessImage[] = [];
  disableSetImageButton = false;
  readonly hostUpdateStateSummaryTableColumnNames = ['state', 'count'];
  hostUpdateStateSummaryTableDataSource =
      new MatTableDataSource<HostUpdateStateSummaryElement>();
  readonly hostCountByVersionTableColumnNames = ['version', 'count'];
  hostCountByVersionTableDataSource =
      new MatTableDataSource<HostCountByHarnessVersionElement>();
  readonly UpdateMode = UpdateMode;
  updatingHostCountInSelectedLab = 0;
  updatingHostCountInSelectedHostGroup = 0;

  private readonly destroy = new ReplaySubject<void>(1);

  @ViewChild(MatPaginator) matPaginator!: MatPaginator;
  @ViewChild(MatSort) matSort!: MatSort;

  get selectedHostGroup() {
    return this.selectedHostGroupValue;
  }

  set selectedHostGroup(value: string) {
    this.selectedHostGroupValue = value;
    if (!this.selectedHostGroup) {
      this.initLabInfo();
      return;
    }
    this.initClusterInfo();
  }

  get labInfo() {
    return this.labInfoValue;
  }

  set labInfo(value: LabInfo|null) {
    this.labInfoValue = value;
    this.updatingHostCountInSelectedLab =
        this.getHostUpdatingCount(value?.hostUpdateStateSummary);
  }

  get clusterInfo() {
    return this.clusterInfoValue;
  }

  set clusterInfo(value: ClusterInfo|null) {
    this.clusterInfoValue = value;
    this.updatingHostCountInSelectedHostGroup =
        this.getHostUpdatingCount(value?.hostUpdateStateSummary);
  }

  constructor(
      public dialogRef: MatDialogRef<HostUpdateDialog>,
      @Inject(MAT_DIALOG_DATA) public data: HostUpdateDialogData,
      private readonly tfcClient: TfcClient,
      private readonly notifier: Notifier,
  ) {
    if (!data.selectedLab) {
      this.dialogRef.close(false);
    }
    this.selectedLab = data.selectedLab;
  }

  ngAfterViewInit() {
    assertRequiredInput(this.matSort, 'matSort', 'hostUpdateDialog');
    assertRequiredInput(this.matPaginator, 'matPaginator', 'hostUpdateDialog');
    this.hostCountByVersionTableDataSource.sort = this.matSort;
    this.hostCountByVersionTableDataSource.paginator = this.matPaginator;
  }

  ngOnInit() {
    this.initLabInfo();
    this.initHostConfigsInLab();
    this.getTestHarnessImagesByTagPrefix();
  }

  ngOnDestroy() {
    this.destroy.next();
    this.destroy.complete();
  }

  initLabInfo() {
    return this.tfcClient.getLabInfo(this.selectedLab)
        .pipe(takeUntil(this.destroy))
        .subscribe(
            (result) => {
              this.labInfo = result;
              this.loadUpdateStateAndVersionCountTables();
            },
            () => {
              this.notifier.showError('Failed to load lab info.');
            });
  }

  initHostConfigsInLab() {
    return this.tfcClient.getHostConfigs(this.selectedLab, DEFAULT_ALL_COUNT)
        .pipe(takeUntil(this.destroy))
        .subscribe(
            (result) => {
              if (!result.host_configs) {
                return;
              }
              // All host group names (including those are not enabled UI
              // update) will be loaded for the purpose of displaying update
              // states and version summaries.
              this.hostGroupNames = [
                ...new Set(
                    result.host_configs.map((config) => config.cluster_name))
              ].sort();
              // Only host configs with UI-Update enabled are loaded for the
              // purpose of triggering updates.
              this.hostConfigsInLab = result.host_configs.filter(
                  (config) => config.enable_ui_update);
            },
            () => {
              this.notifier.showError('Failed to load host configs.');
            });
  }

  initClusterInfo() {
    return this.tfcClient.getClusterInfo(this.selectedHostGroup)
        .pipe(takeUntil(this.destroy))
        .subscribe(
            (result) => {
              this.clusterInfo = result;
              this.loadUpdateStateAndVersionCountTables();
            },
            () => {
              this.notifier.showError('Failed to load host group info.');
            });
  }

  refreshSummaryTables() {
    if (this.selectedHostGroup) {
      this.initClusterInfo();
    } else {
      this.initLabInfo();
    }
  }

  getTestHarnessImagesByTagPrefix() {
    return this.tfcClient
        .getTestHarnessImages(
            this.imageTagPrefix, DEFAULT_TEST_HARNESS_IMAGE_COUNT)
        .pipe(takeUntil(this.destroy))
        .subscribe(
            (result) => {
              if (!result.images) {
                return;
              }
              this.testHarnessImages = result.images;
            },
            () => {
              this.notifier.showError('Failed to load test harness images.');
            });
  }

  getHostUpdatingCount(summary?: HostUpdateStateSummary|null): number {
    return summary ?
        summary.syncing + summary.shuttingDown + summary.restarting :
        0;
  }

  loadHostConfigsInSelectedHostGroup() {
    this.candidateHostConfigs = this.selectedHostGroup ?
        this.hostConfigsInLab.filter(
            (config) => config.cluster_name === this.selectedHostGroup) :
        this.hostConfigsInLab;
    this.hostNames =
        this.candidateHostConfigs.map((config) => config.hostname).sort();
  }

  private getSelectableTargetVersions(hostUpdateStateSummariesByVersion:
                                          HostUpdateStateSummary[]|
                                      undefined): string[] {
    if (!hostUpdateStateSummariesByVersion) {
      return [];
    }
    const targetVersions = hostUpdateStateSummariesByVersion
                               .map(summary => summary.targetVersion || '')
                               .filter(Boolean)
                               .sort()
                               .reverse();
    targetVersions.unshift('');
    return targetVersions;
  }

  private getHostUpdateStateSummaryForDisplay(
      hostUpdateStateSummariesByVersion: HostUpdateStateSummary[]|undefined,
      fullHostUpdateStateSummary: HostUpdateStateSummary|
      null): HostUpdateStateSummary|null|undefined {
    let summary;
    if (this.selectedTargetVersion && hostUpdateStateSummariesByVersion) {
      let found = false;
      for (const summaryWithVersion of hostUpdateStateSummariesByVersion) {
        if (summaryWithVersion.targetVersion === this.selectedTargetVersion) {
          summary = summaryWithVersion;
          found = true;
          break;
        }
      }
      if (!found) {
        this.notifier.showError(`No host update summary is found for
              selected version ${this.selectedTargetVersion}.
              Displaying summary for all versions as a whole.`);
        summary = fullHostUpdateStateSummary;
        this.selectedTargetVersion = '';
      }
    } else {
      summary = fullHostUpdateStateSummary;
      this.selectedTargetVersion = '';
    }
    return summary;
  }

  loadUpdateStateAndVersionCountTables() {
    let summary;
    let versionCount;
    if (this.selectedHostGroup) {
      if (!this.clusterInfo) {
        return;
      }
      this.selectableTargetVersions = this.getSelectableTargetVersions(
          this.clusterInfo.hostUpdateStateSummariesByVersion);

      summary = this.getHostUpdateStateSummaryForDisplay(
          this.clusterInfo.hostUpdateStateSummariesByVersion,
          this.clusterInfo.hostUpdateStateSummary);
      versionCount = this.clusterInfo.hostCountByHarnessVersion;
    } else {
      if (!this.labInfo) {
        return;
      }
      this.selectableTargetVersions = this.getSelectableTargetVersions(
          this.labInfo.hostUpdateStateSummariesByVersion);
      summary = this.getHostUpdateStateSummaryForDisplay(
          this.labInfo.hostUpdateStateSummariesByVersion,
          this.labInfo.hostUpdateStateSummary);
      versionCount = this.labInfo.hostCountByHarnessVersion;
    }
    if (summary) {
      this.hostUpdateStateSummaryTableDataSource.data = [
        {state: HostUpdateState.PENDING, count: summary.pending},
        {state: HostUpdateState.SYNCING, count: summary.syncing},
        {state: HostUpdateState.SHUTTING_DOWN, count: summary.shuttingDown},
        {state: HostUpdateState.RESTARTING, count: summary.restarting},
        {state: HostUpdateState.SUCCEEDED, count: summary.succeeded},
        {state: HostUpdateState.TIMED_OUT, count: summary.timedOut},
        {state: HostUpdateState.ERRORED, count: summary.errored},
        {state: HostUpdateState.UNKNOWN, count: summary.unknown},
      ];
    }
    if (versionCount) {
      this.hostCountByVersionTableDataSource.data = versionCount.map(x => {
        return {version: x.key, count: Number(x.value)};
      });
    }
  }

  setSelectedHosts(hostNames: string[]) {
    this.selectedHosts =
        hostNames.includes(ALL_OPTIONS_VALUE) ? this.hostNames : hostNames;
  }

  onModeChange($event: MatRadioChange) {
    if ($event.value === UpdateMode.LAB) {
      this.selectedHostGroup = '';
      this.selectedHosts = [];
    } else if ($event.value === UpdateMode.HOST_GROUP) {
      this.selectedHosts = [];
    }
    this.loadHostConfigsInSelectedHostGroup();
  }

  getBatchUpdateHostMetadataRequest(): BatchUpdateHostMetadataRequest|null {
    if (!this.selectedImage) {
      this.notifier.showError('No test harness image is selected.');
      return null;
    }
    const selectedImageName = `${this.selectedImage.repo_name}:${
        this.selectedImage.test_harness_version}`;
    let hostnames: string[];
    if (this.selectedMode === UpdateMode.LAB) {
      hostnames = this.hostConfigsInLab.map(config => config.hostname);
    } else if (this.selectedMode === UpdateMode.HOST_GROUP) {
      hostnames = this.candidateHostConfigs.map(config => config.hostname);
    } else {
      hostnames = this.selectedHosts;
    }
    if (!hostnames || hostnames.length === 0) {
      this.notifier.showError('No host is selected.');
      return null;
    }
    return {
      hostnames,
      test_harness_image: selectedImageName,
    };
  }

  onConfirmSetImage() {
    this.disableSetImageButton = true;
    const requestBody = this.getBatchUpdateHostMetadataRequest();
    if (!requestBody) {
      this.disableSetImageButton = false;
      return;
    }
    this.tfcClient.batchUpdateHostMetadata(requestBody)
        .pipe(
            takeUntil(this.destroy),
            finalize(() => {
              this.disableSetImageButton = false;
            }),
            )
        .subscribe(
            () => {
              this.notifier.showMessage(`Successfully set image <${
                  requestBody.test_harness_image}> on hosts: [${
                  requestBody.hostnames.join(', ')}]`);
            },
            (err) => {
              let message: string;
              if (err.error?.error?.errors) {
                // In production env, the error comes for TFC service behind
                // the API proxy, so it stores a structured error.
                message = err.error.error.errors[0].message;
              } else {
                // In dev or test env, the error is thrown directly from
                // the proxy request.
                message = err.message;
              }
              this.notifier.showError(
                  `Error when setting the image: ${message}`);
            },
        );
  }
}
