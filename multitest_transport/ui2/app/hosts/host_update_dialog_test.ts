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
import {HttpErrorResponse} from '@angular/common/http';
import {HttpClientTestingModule} from '@angular/common/http/testing';
import {ComponentFixture, TestBed} from '@angular/core/testing';
import {MAT_DIALOG_DATA, MatDialogRef} from '@angular/material/dialog';
import {MatRadioButton, MatRadioChange} from '@angular/material/radio';
import {NoopAnimationsModule} from '@angular/platform-browser/animations';
import {ActivatedRoute, Router} from '@angular/router';
import {of as observableOf, throwError} from 'rxjs';

import {APP_DATA} from '../services';
import {convertToHostUpdateStateSummary} from '../services/mtt_lab_models';
import {Notifier} from '../services/notifier';
import {TfcClient} from '../services/tfc_client';
import {HostConfig, HostUpdateState, TestHarnessImage} from '../services/tfc_models';
import {ActivatedRouteStub} from '../testing/activated_route_stub';
import {newMockAppData, newMockHostConfig, newMockHostConfigList, newMockHostUpdateStateSummary, newMockTestHarnessImage, newMockTestHarnessImageList} from '../testing/mtt_lab_mocks';

import {HostUpdateDialog, HostUpdateDialogData, UpdateMode} from './host_update_dialog';
import {HostsModule} from './hosts_module';

describe('HostUpdateDialog', () => {
  let routerSpy: jasmine.SpyObj<Router>;
  let tfcClient: jasmine.SpyObj<TfcClient>;
  let notifier: jasmine.SpyObj<Notifier>;
  let dialogRefSpy: jasmine.SpyObj<MatDialogRef<HostUpdateDialog>>;
  let hostUpdateDialog: HostUpdateDialog;
  let hostUpdateDialogFixture: ComponentFixture<HostUpdateDialog>;

  const dialogData: HostUpdateDialogData = {selectedLab: 'lab1'};
  const hostConfigs: HostConfig[] = [
    newMockHostConfig('host-1', 'lab1', 'cluster-1', true),
    newMockHostConfig('host-2', 'lab1', 'cluster-1', true),
    newMockHostConfig('host-3', 'lab1', 'cluster-1', true),
    newMockHostConfig('host-4', 'lab1', 'cluster-2', true),
    newMockHostConfig('host-5', 'lab1', 'cluster-2', true),
    newMockHostConfig('host-6', 'lab1', 'cluster-2', true),
  ];
  const testHarnessImages: TestHarnessImage[] = [
    newMockTestHarnessImage(
        undefined, 'digest-1', 'repo', ['tag-1'], undefined, 'v1'),
    newMockTestHarnessImage(
        undefined, 'digest-2', undefined, ['tag-2'], undefined, 'v2'),
    newMockTestHarnessImage(
        undefined, 'digest-3', undefined, ['tag-3'], undefined, 'v3'),
    newMockTestHarnessImage(
        undefined, 'digest-4', undefined, ['tag-4'], undefined, 'v4'),
  ];

  beforeEach((() => {
    dialogRefSpy = jasmine.createSpyObj<MatDialogRef<HostUpdateDialog>>(
        'dialogRefSpy', ['close']);
    notifier = jasmine.createSpyObj<Notifier>(
        'notifier', ['showMessage', 'showError']);
    routerSpy =
        jasmine.createSpyObj<Router>('Router', ['navigate', 'navigateByUrl']);
    const activatedRouteSpy = new ActivatedRouteStub({});
    tfcClient = jasmine.createSpyObj('tfcClient', {
      getLabInfo: observableOf({
        labName: 'lab1',
        owners: ['user1'],
      }),
      getClusterInfo: observableOf({}),
      getHostConfigs: observableOf({}),
      getTestHarnessImages: observableOf({}),
      batchUpdateHostMetadata: observableOf({}),
    });

    TestBed.configureTestingModule({
      imports: [
        NoopAnimationsModule,
        HostsModule,
        HttpClientTestingModule,
      ],
      providers: [
        {provide: MAT_DIALOG_DATA, useValue: dialogData},
        {provide: APP_DATA, useValue: newMockAppData()},
        {provide: MatDialogRef, useValue: dialogRefSpy},
        {provide: Notifier, useValue: notifier},
        {provide: Router, useValue: routerSpy},
        {provide: ActivatedRoute, useValue: activatedRouteSpy},
        {provide: TfcClient, useValue: tfcClient},
      ],
    });
    hostUpdateDialogFixture = TestBed.createComponent(HostUpdateDialog);
    hostUpdateDialog = hostUpdateDialogFixture.componentInstance;
  }));

  it('initializes a component', () => {
    hostUpdateDialogFixture.detectChanges();
    expect(hostUpdateDialog).toBeTruthy();
  });

  it('gets lab info correctly', () => {
    const hostCountByHarnessVersion = [
      {key: 'v1', value: '2'},
      {key: 'v2', value: '2'},
    ];
    tfcClient.getLabInfo.and.returnValue(observableOf({
      labName: 'lab1',
      owners: ['user1'],
      hostUpdateStateSummary:
          convertToHostUpdateStateSummary(newMockHostUpdateStateSummary()),
      hostCountByHarnessVersion,
    }));
    hostUpdateDialogFixture.detectChanges();
    hostUpdateDialogFixture.whenStable().then(() => {
      expect(hostUpdateDialog.labInfo).toBeTruthy();
      expect(hostUpdateDialog.labInfo?.labName).toEqual('lab1');
      expect(hostUpdateDialog.labInfo?.owners).toEqual(['user1']);
      expect(hostUpdateDialog.labInfo?.hostUpdateStateSummary).toBeTruthy();
      expect(hostUpdateDialog.labInfo?.hostCountByHarnessVersion)
          .toEqual(hostCountByHarnessVersion);
    });
  });

  it('calculate HostUpdating count correctly', () => {
    const hostUpdateStateSummary =
        convertToHostUpdateStateSummary(newMockHostUpdateStateSummary(
            '30', '5', '2', '10', '2', '1', '1', '0'));
    expect(hostUpdateDialog.getHostUpdatingCount(hostUpdateStateSummary))
        .toBe(14);
    expect(hostUpdateDialog.getHostUpdatingCount(null)).toBe(0);
  });

  it('gets host configs correctly', () => {
    const hostConfigList = newMockHostConfigList(hostConfigs);
    tfcClient.getHostConfigs.and.returnValue(observableOf(hostConfigList));
    hostUpdateDialogFixture.detectChanges();
    hostUpdateDialogFixture.whenStable().then(() => {
      expect(hostUpdateDialog.hostConfigsInLab).toBeTruthy();
      expect(hostUpdateDialog.hostConfigsInLab).toEqual(hostConfigs);
    });
  });

  it('display all host groups and sorts them in alphabetical order.', () => {
    const hostConfigsNotOrdered: HostConfig[] = [
      newMockHostConfig('host-1', 'lab1', 'cluster-5', true),
      newMockHostConfig('host-2', 'lab1', 'cluster-3', true),
      newMockHostConfig('host-3', 'lab1', 'cluster-4', true),
      newMockHostConfig('host-4', 'lab1', 'cluster-2', false),
      newMockHostConfig('host-5', 'lab1', 'cluster-1', false),
      newMockHostConfig('host-6', 'lab1', 'cluster-4', true),
    ];
    const hostConfigList = newMockHostConfigList(hostConfigsNotOrdered);
    tfcClient.getHostConfigs.and.returnValue(observableOf(hostConfigList));

    hostUpdateDialogFixture.detectChanges();

    hostUpdateDialogFixture.whenStable().then(() => {
      expect(hostUpdateDialog.hostGroupNames).toEqual([
        'cluster-1',
        'cluster-2',
        'cluster-3',
        'cluster-4',
        'cluster-5',
      ]);
    });
  });

  it('gets candidate host configs when host group is selected', () => {
    hostUpdateDialog.hostConfigsInLab = hostConfigs;
    hostUpdateDialog.selectedHostGroup = 'cluster-2';

    hostUpdateDialog.loadHostConfigsInSelectedHostGroup();

    expect(hostUpdateDialog.candidateHostConfigs).toEqual(hostConfigs.slice(3));
  });

  it('gets candidate host configs when host group is unselected', () => {
    hostUpdateDialog.hostConfigsInLab = hostConfigs;
    hostUpdateDialog.selectedHostGroup = '';

    hostUpdateDialog.loadHostConfigsInSelectedHostGroup();

    expect(hostUpdateDialog.candidateHostConfigs).toEqual(hostConfigs);
  });

  it('sorts host names in alphabetical order.', () => {
    const hostConfigsNotOrdered: HostConfig[] = [
      newMockHostConfig('host-2', 'lab1', 'cluster-1', true),
      newMockHostConfig('host-1', 'lab1', 'cluster-1', true),
      newMockHostConfig('host-3', 'lab1', 'cluster-1', true),
      newMockHostConfig('host-5', 'lab1', 'cluster-2', true),
      newMockHostConfig('host-6', 'lab1', 'cluster-2', true),
      newMockHostConfig('host-4', 'lab1', 'cluster-2', true),
    ];
    hostUpdateDialog.hostConfigsInLab = hostConfigsNotOrdered;
    hostUpdateDialog.selectedHostGroup = '';

    hostUpdateDialog.loadHostConfigsInSelectedHostGroup();

    expect(hostUpdateDialog.hostNames).toEqual([
      'host-1',
      'host-2',
      'host-3',
      'host-4',
      'host-5',
      'host-6',
    ]);
  });

  it('selects hosts correctly', () => {
    const hostNames = ['host-1', 'host-2'];
    hostUpdateDialog.setSelectedHosts(hostNames);
    expect(hostUpdateDialog.selectedHosts).toEqual(hostNames);
  });

  it('gets test harness images correctly', () => {
    const testHarnessImageList = newMockTestHarnessImageList(testHarnessImages);
    tfcClient.getTestHarnessImages.and.returnValue(
        observableOf(testHarnessImageList));
    hostUpdateDialogFixture.detectChanges();
    hostUpdateDialogFixture.whenStable().then(() => {
      expect(hostUpdateDialog.testHarnessImages).toBeTruthy();
      expect(hostUpdateDialog.testHarnessImages).toEqual(testHarnessImages);
    });
  });

  it('resets data correctly when select lab update mode', () => {
    hostUpdateDialog.hostConfigsInLab = hostConfigs;
    hostUpdateDialog.selectedHostGroup = 'cluster-2';
    hostUpdateDialog.selectedHosts = ['host-4', 'host-5'];
    hostUpdateDialog.onModeChange(
        new MatRadioChange({} as MatRadioButton, UpdateMode.LAB));
    expect(hostUpdateDialog.selectedHostGroup).toEqual('');
    expect(hostUpdateDialog.selectedHosts).toEqual([]);
  });

  it('resets data correctly when select host group update mode', () => {
    hostUpdateDialog.hostConfigsInLab = hostConfigs;
    hostUpdateDialog.selectedHostGroup = 'cluster-2';
    hostUpdateDialog.selectedHosts = ['host-4', 'host-5'];
    hostUpdateDialog.onModeChange(
        new MatRadioChange({} as MatRadioButton, UpdateMode.HOST_GROUP));
    expect(hostUpdateDialog.selectedHostGroup).toEqual('cluster-2');
    expect(hostUpdateDialog.selectedHosts).toEqual([]);
  });

  describe('loadUpdateStateAndVersionCountTables', () => {
    it('loads update state and version counts tables in the lab correctly',
       () => {
         hostUpdateDialog.labInfo = {
           labName: 'lab1',
           owners: ['user1'],
           hostUpdateStateSummary:
               convertToHostUpdateStateSummary(newMockHostUpdateStateSummary(
                   '30', '5', '2', '10', '10', '1', '1', '1', '0')),
           hostCountByHarnessVersion: [
             {key: 'v1', value: '2'},
             {key: 'v2', value: '2'},
           ],
         };
         hostUpdateDialog.loadUpdateStateAndVersionCountTables();
         expect(hostUpdateDialog.hostUpdateStateSummaryTableDataSource.data)
             .toEqual([
               {state: HostUpdateState.PENDING, count: 5},
               {state: HostUpdateState.SYNCING, count: 2},
               {state: HostUpdateState.SHUTTING_DOWN, count: 10},
               {state: HostUpdateState.RESTARTING, count: 10},
               {state: HostUpdateState.SUCCEEDED, count: 1},
               {state: HostUpdateState.TIMED_OUT, count: 1},
               {state: HostUpdateState.ERRORED, count: 1},
               {state: HostUpdateState.UNKNOWN, count: 0},
             ]);
         expect(hostUpdateDialog.hostCountByVersionTableDataSource.data)
             .toEqual([
               {version: 'v1', count: 2},
               {version: 'v2', count: 2},
             ]);
       });

    it('loads update state and version counts tables in host group correctly',
       () => {
         hostUpdateDialog.selectedHostGroup = 'hostGroup1';
         hostUpdateDialog.clusterInfo = {
           clusterId: 'hostGroup1',
           hostUpdateStateSummary:
               convertToHostUpdateStateSummary(newMockHostUpdateStateSummary(
                   '30', '5', '2', '10', '10', '1', '1', '1', '0')),
           hostCountByHarnessVersion: [
             {key: 'v1', value: '2'},
             {key: 'v2', value: '5'},
           ],
         };
         hostUpdateDialog.loadUpdateStateAndVersionCountTables();
         expect(hostUpdateDialog.hostUpdateStateSummaryTableDataSource.data)
             .toEqual([
               {state: HostUpdateState.PENDING, count: 5},
               {state: HostUpdateState.SYNCING, count: 2},
               {state: HostUpdateState.SHUTTING_DOWN, count: 10},
               {state: HostUpdateState.RESTARTING, count: 10},
               {state: HostUpdateState.SUCCEEDED, count: 1},
               {state: HostUpdateState.TIMED_OUT, count: 1},
               {state: HostUpdateState.ERRORED, count: 1},
               {state: HostUpdateState.UNKNOWN, count: 0},
             ]);
         expect(hostUpdateDialog.hostCountByVersionTableDataSource.data)
             .toEqual([
               {version: 'v1', count: 2},
               {version: 'v2', count: 5},
             ]);
       });

    it('modifies table data sources when selected host group changes', () => {
      hostUpdateDialog.selectedHostGroup = '';
      tfcClient.getClusterInfo.withArgs('hostGroup1')
          .and
          .returnValue(observableOf({
            clusterId: 'hostGroup1',
            hostUpdateStateSummary:
                convertToHostUpdateStateSummary(newMockHostUpdateStateSummary(
                    '30', '5', '2', '10', '10', '1', '1', '1', '0')),
            hostCountByHarnessVersion: [
              {key: 'v1', value: '3'},
              {key: 'v2', value: '2'},
            ],
          }))
          .withArgs('hostGroup2')
          .and.returnValue(observableOf({
            clusterId: 'hostGroup2',
            hostUpdateStateSummary:
                convertToHostUpdateStateSummary(newMockHostUpdateStateSummary(
                    '38', '6', '3', '11', '11', '2', '2', '2', '1')),
            hostCountByHarnessVersion: [
              {key: 'v3', value: '3'},
              {key: 'v4', value: '2'},
            ],
          }));
      hostUpdateDialog.selectedHostGroup = 'hostGroup1';
      hostUpdateDialogFixture.detectChanges();
      hostUpdateDialogFixture.whenStable()
          .then(() => {
            expect(hostUpdateDialog.hostUpdateStateSummaryTableDataSource.data)
                .toEqual([
                  {state: HostUpdateState.PENDING, count: 5},
                  {state: HostUpdateState.SYNCING, count: 2},
                  {state: HostUpdateState.SHUTTING_DOWN, count: 10},
                  {state: HostUpdateState.RESTARTING, count: 10},
                  {state: HostUpdateState.SUCCEEDED, count: 1},
                  {state: HostUpdateState.TIMED_OUT, count: 1},
                  {state: HostUpdateState.ERRORED, count: 1},
                  {state: HostUpdateState.UNKNOWN, count: 0},
                ]);
            expect(hostUpdateDialog.hostCountByVersionTableDataSource.data)
                .toEqual([
                  {version: 'v1', count: 3},
                  {version: 'v2', count: 2},
                ]);
          })
          .then(() => {
            hostUpdateDialog.selectedHostGroup = 'hostGroup2';
            hostUpdateDialogFixture.detectChanges();
            hostUpdateDialogFixture.whenStable().then(() => {
              expect(
                  hostUpdateDialog.hostUpdateStateSummaryTableDataSource.data)
                  .toEqual([
                    {state: HostUpdateState.PENDING, count: 6},
                    {state: HostUpdateState.SYNCING, count: 3},
                    {state: HostUpdateState.SHUTTING_DOWN, count: 11},
                    {state: HostUpdateState.RESTARTING, count: 11},
                    {state: HostUpdateState.SUCCEEDED, count: 2},
                    {state: HostUpdateState.TIMED_OUT, count: 2},
                    {state: HostUpdateState.ERRORED, count: 2},
                    {state: HostUpdateState.UNKNOWN, count: 1},
                  ]);
              expect(hostUpdateDialog.hostCountByVersionTableDataSource.data)
                  .toEqual([
                    {version: 'v3', count: 3},
                    {version: 'v4', count: 2},
                  ]);
            });
          });
    });

    it('modifies table data sources when selected host group removes', () => {
      tfcClient.getLabInfo.and.returnValue(observableOf({
        labName: 'lab1',
        owners: ['user1'],
        hostUpdateStateSummary:
            convertToHostUpdateStateSummary(newMockHostUpdateStateSummary(
                '38', '6', '3', '11', '11', '2', '2', '2', '1')),
        hostCountByHarnessVersion: [
          {key: 'v3', value: '3'},
          {key: 'v4', value: '2'},
        ],
      }));
      hostUpdateDialog.selectedHostGroup = 'hostGroup1';
      hostUpdateDialog.clusterInfo = {
        clusterId: 'hostGroup1',
        hostUpdateStateSummary:
            convertToHostUpdateStateSummary(newMockHostUpdateStateSummary(
                '30', '5', '2', '10', '10', '1', '1', '1', '0')),
        hostCountByHarnessVersion: [
          {key: 'v1', value: '2'},
          {key: 'v2', value: '5'},
        ],
      };

      hostUpdateDialog.loadUpdateStateAndVersionCountTables();

      expect(hostUpdateDialog.hostUpdateStateSummaryTableDataSource.data)
          .toEqual([
            {state: HostUpdateState.PENDING, count: 5},
            {state: HostUpdateState.SYNCING, count: 2},
            {state: HostUpdateState.SHUTTING_DOWN, count: 10},
            {state: HostUpdateState.RESTARTING, count: 10},
            {state: HostUpdateState.SUCCEEDED, count: 1},
            {state: HostUpdateState.TIMED_OUT, count: 1},
            {state: HostUpdateState.ERRORED, count: 1},
            {state: HostUpdateState.UNKNOWN, count: 0},
          ]);
      expect(hostUpdateDialog.hostCountByVersionTableDataSource.data).toEqual([
        {version: 'v1', count: 2},
        {version: 'v2', count: 5},
      ]);
      hostUpdateDialog.selectedHostGroup = '';
      hostUpdateDialogFixture.detectChanges();
      hostUpdateDialogFixture.whenStable().then(() => {
        expect(hostUpdateDialog.hostUpdateStateSummaryTableDataSource.data)
            .toEqual([
              {state: HostUpdateState.PENDING, count: 6},
              {state: HostUpdateState.SYNCING, count: 3},
              {state: HostUpdateState.SHUTTING_DOWN, count: 11},
              {state: HostUpdateState.RESTARTING, count: 11},
              {state: HostUpdateState.SUCCEEDED, count: 2},
              {state: HostUpdateState.TIMED_OUT, count: 2},
              {state: HostUpdateState.ERRORED, count: 2},
              {state: HostUpdateState.UNKNOWN, count: 1},
            ]);
        expect(hostUpdateDialog.hostCountByVersionTableDataSource.data)
            .toEqual([
              {version: 'v3', count: 3},
              {version: 'v4', count: 2},
            ]);
      });
    });

    it('loads lab update state summary for selected version', () => {
      hostUpdateDialog.labInfo = {
        labName: 'lab1',
        owners: ['user1'],
        hostUpdateStateSummary:
            convertToHostUpdateStateSummary(newMockHostUpdateStateSummary(
                '30', '5', '2', '10', '10', '1', '1', '1', '0')),
        hostCountByHarnessVersion: [
          {key: 'v1', value: '2'},
          {key: 'v2', value: '2'},
        ],
        hostUpdateStateSummariesByVersion: [
          convertToHostUpdateStateSummary(newMockHostUpdateStateSummary(
              '8', '1', '1', '1', '1', '1', '1', '1', '1', undefined, 'v1')),
          convertToHostUpdateStateSummary(newMockHostUpdateStateSummary(
              '22', '3', '1', '9', '9', '0', '0', '0', '0', undefined, 'v2')),
        ],
      };

      hostUpdateDialog.selectedTargetVersion = 'v1';
      hostUpdateDialog.loadUpdateStateAndVersionCountTables();

      expect(hostUpdateDialog.hostUpdateStateSummaryTableDataSource.data)
          .toEqual([
            {state: HostUpdateState.PENDING, count: 1},
            {state: HostUpdateState.SYNCING, count: 1},
            {state: HostUpdateState.SHUTTING_DOWN, count: 1},
            {state: HostUpdateState.RESTARTING, count: 1},
            {state: HostUpdateState.SUCCEEDED, count: 1},
            {state: HostUpdateState.TIMED_OUT, count: 1},
            {state: HostUpdateState.ERRORED, count: 1},
            {state: HostUpdateState.UNKNOWN, count: 1},
          ]);

      hostUpdateDialog.selectedTargetVersion = 'v2';
      hostUpdateDialog.loadUpdateStateAndVersionCountTables();
      expect(hostUpdateDialog.hostUpdateStateSummaryTableDataSource.data)
          .toEqual([
            {state: HostUpdateState.PENDING, count: 3},
            {state: HostUpdateState.SYNCING, count: 1},
            {state: HostUpdateState.SHUTTING_DOWN, count: 9},
            {state: HostUpdateState.RESTARTING, count: 9},
            {state: HostUpdateState.SUCCEEDED, count: 0},
            {state: HostUpdateState.TIMED_OUT, count: 0},
            {state: HostUpdateState.ERRORED, count: 0},
            {state: HostUpdateState.UNKNOWN, count: 0},
          ]);
    });

    it('loads full lab update state summary if no valid version is selected',
       () => {
         hostUpdateDialog.labInfo = {
           labName: 'lab1',
           owners: ['user1'],
           hostUpdateStateSummary:
               convertToHostUpdateStateSummary(newMockHostUpdateStateSummary(
                   '30', '5', '2', '10', '10', '1', '1', '1', '0')),
           hostCountByHarnessVersion: [
             {key: 'v1', value: '2'},
             {key: 'v2', value: '2'},
           ],
           hostUpdateStateSummariesByVersion: [
             convertToHostUpdateStateSummary(newMockHostUpdateStateSummary(
                 '8', '1', '1', '1', '1', '1', '1', '1', '1', undefined, 'v1')),
             convertToHostUpdateStateSummary(newMockHostUpdateStateSummary(
                 '22', '3', '1', '9', '9', '0', '0', '0', '0', undefined,
                 'v2')),
           ],
         };

         hostUpdateDialog.selectedTargetVersion = 'v3';
         hostUpdateDialog.loadUpdateStateAndVersionCountTables();

         expect(hostUpdateDialog.hostUpdateStateSummaryTableDataSource.data)
             .toEqual([
               {state: HostUpdateState.PENDING, count: 5},
               {state: HostUpdateState.SYNCING, count: 2},
               {state: HostUpdateState.SHUTTING_DOWN, count: 10},
               {state: HostUpdateState.RESTARTING, count: 10},
               {state: HostUpdateState.SUCCEEDED, count: 1},
               {state: HostUpdateState.TIMED_OUT, count: 1},
               {state: HostUpdateState.ERRORED, count: 1},
               {state: HostUpdateState.UNKNOWN, count: 0},
             ]);
         expect(hostUpdateDialog.selectedTargetVersion).toEqual('');
       });

    it('loads host group update state summary for selected version', () => {
      hostUpdateDialog.selectedHostGroup = 'hostGroup1';
      hostUpdateDialog.clusterInfo = {
        clusterId: 'hostGroup1',
        hostUpdateStateSummary:
            convertToHostUpdateStateSummary(newMockHostUpdateStateSummary(
                '30', '5', '2', '10', '10', '1', '1', '1', '0')),
        hostCountByHarnessVersion: [
          {key: 'v1', value: '2'},
          {key: 'v2', value: '2'},
        ],
        hostUpdateStateSummariesByVersion: [
          convertToHostUpdateStateSummary(newMockHostUpdateStateSummary(
              '8', '1', '1', '1', '1', '1', '1', '1', '1', undefined, 'v1')),
          convertToHostUpdateStateSummary(newMockHostUpdateStateSummary(
              '22', '3', '1', '9', '9', '0', '0', '0', '0', undefined, 'v2')),
        ],
      };

      hostUpdateDialog.selectedTargetVersion = 'v1';
      hostUpdateDialog.loadUpdateStateAndVersionCountTables();

      expect(hostUpdateDialog.hostUpdateStateSummaryTableDataSource.data)
          .toEqual([
            {state: HostUpdateState.PENDING, count: 1},
            {state: HostUpdateState.SYNCING, count: 1},
            {state: HostUpdateState.SHUTTING_DOWN, count: 1},
            {state: HostUpdateState.RESTARTING, count: 1},
            {state: HostUpdateState.SUCCEEDED, count: 1},
            {state: HostUpdateState.TIMED_OUT, count: 1},
            {state: HostUpdateState.ERRORED, count: 1},
            {state: HostUpdateState.UNKNOWN, count: 1},
          ]);

      hostUpdateDialog.selectedTargetVersion = 'v2';
      hostUpdateDialog.loadUpdateStateAndVersionCountTables();
      expect(hostUpdateDialog.hostUpdateStateSummaryTableDataSource.data)
          .toEqual([
            {state: HostUpdateState.PENDING, count: 3},
            {state: HostUpdateState.SYNCING, count: 1},
            {state: HostUpdateState.SHUTTING_DOWN, count: 9},
            {state: HostUpdateState.RESTARTING, count: 9},
            {state: HostUpdateState.SUCCEEDED, count: 0},
            {state: HostUpdateState.TIMED_OUT, count: 0},
            {state: HostUpdateState.ERRORED, count: 0},
            {state: HostUpdateState.UNKNOWN, count: 0},
          ]);
    });
  });

  describe('getBatchUpdateHostMetadataRequest', () => {
    beforeEach(() => {
      hostUpdateDialog.selectedImage = testHarnessImages[0];
      hostUpdateDialog.hostConfigsInLab = hostConfigs;
    });

    it('throws error when no image is selected', () => {
      hostUpdateDialog.selectedImage = null;

      expect(hostUpdateDialog.getBatchUpdateHostMetadataRequest()).toBeNull();
      expect(notifier.showError)
          .toHaveBeenCalledOnceWith('No test harness image is selected.');
    });

    it('throws error when no host is selected', () => {
      hostUpdateDialog.selectedMode = UpdateMode.HOSTS;
      hostUpdateDialog.selectedHosts = [];

      expect(hostUpdateDialog.getBatchUpdateHostMetadataRequest()).toBeNull();
      expect(notifier.showError)
          .toHaveBeenCalledOnceWith('No host is selected.');
    });

    it('selects an entire lab correctly', () => {
      hostUpdateDialog.selectedMode = UpdateMode.LAB;

      const expectedRequest = {
        test_harness_image: 'repo:v1',
        hostnames: [
          'host-1',
          'host-2',
          'host-3',
          'host-4',
          'host-5',
          'host-6',
        ],
      };

      expect(hostUpdateDialog.getBatchUpdateHostMetadataRequest())
          .toEqual(expectedRequest);
    });

    it('selects an entire host group correctly', () => {
      hostUpdateDialog.selectedMode = UpdateMode.HOST_GROUP;
      hostUpdateDialog.selectedHostGroup = 'cluster-2';

      hostUpdateDialog.loadHostConfigsInSelectedHostGroup();

      const expectedRequest = {
        test_harness_image: 'repo:v1',
        hostnames: [
          'host-4',
          'host-5',
          'host-6',
        ],
      };

      expect(hostUpdateDialog.getBatchUpdateHostMetadataRequest())
          .toEqual(expectedRequest);
    });

    it('selects hosts correctly', () => {
      hostUpdateDialog.selectedMode = UpdateMode.HOSTS;
      hostUpdateDialog.selectedHosts = ['host-1', 'host-4'];

      const expectedRequest = {
        test_harness_image: 'repo:v1',
        hostnames: [
          'host-1',
          'host-4',
        ],
      };

      expect(hostUpdateDialog.getBatchUpdateHostMetadataRequest())
          .toEqual(expectedRequest);
    });
  });

  describe('onConfirmSetImage', () => {
    beforeEach(() => {
      hostUpdateDialog.selectedImage = testHarnessImages[0];
      hostUpdateDialog.selectedMode = UpdateMode.LAB;
    });

    it('reenables confirmation button if no hosts are selected', () => {
      hostUpdateDialog.hostConfigsInLab = [];

      hostUpdateDialog.onConfirmSetImage();

      expect(hostUpdateDialog.disableSetImageButton).toBeFalse();
    });

    it('submits set image confirmation request correctly', () => {
      hostUpdateDialog.hostConfigsInLab = hostConfigs.slice(0, 2);
      const observable = tfcClient.batchUpdateHostMetadata(
          // TODO: Remove any after Jasmine upgrade is in. Argument
          // of type 'BatchUpdateHostMetadataRequest | null' is not assignable
          // to parameter of type 'BatchUpdateHostMetadataRequest'.
          hostUpdateDialog.getBatchUpdateHostMetadataRequest() as
          AnyDuringJasmineApril2021Migration);

      hostUpdateDialog.onConfirmSetImage();

      observable.subscribe(() => {
        expect(notifier.showMessage)
            .toHaveBeenCalledOnceWith(
                'Successfully set image <repo:v1> on hosts: [host-1, host-2]');
      });
    });

    it('submits set image confirmation request correctly', () => {
      hostUpdateDialog.hostConfigsInLab = hostConfigs.slice(0, 2);
      tfcClient.batchUpdateHostMetadata.and.returnValue(
          throwError(new HttpErrorResponse({
            status: 400,
            statusText: 'Bad Request: some error message',
          })));
      const observable = tfcClient.batchUpdateHostMetadata(
          // TODO: Remove any after Jasmine upgrade is in. Argument
          // of type 'BatchUpdateHostMetadataRequest | null' is not assignable
          // to parameter of type 'BatchUpdateHostMetadataRequest'.
          hostUpdateDialog.getBatchUpdateHostMetadataRequest() as
          AnyDuringJasmineApril2021Migration);
      const expectedErrorMessage = 'Error when setting the image: ' +
          'Http failure response for (unknown url): ' +
          '400 Bad Request: some error message';

      hostUpdateDialog.onConfirmSetImage();

      observable.subscribe(() => {}, () => {
        expect(notifier.showError)
            .toHaveBeenCalledOnceWith(expectedErrorMessage);
      });
    });
  });
});
