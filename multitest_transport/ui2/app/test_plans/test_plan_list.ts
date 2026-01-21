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
import {Component, Input, OnDestroy, OnInit, ViewChild, inject} from '@angular/core';
import {MatTable, MatTableDataSource} from '@angular/material/table';
import {Router} from '@angular/router';
import {ReplaySubject} from 'rxjs';
import {finalize, takeUntil} from 'rxjs/operators';

import {MttClient} from '../services/mtt_client';
import {TestPlan} from '../services/mtt_models';
import {Notifier} from '../services/notifier';
import {OverflowListType} from '../shared/overflow_list';
import {buildApiErrorMessage} from '../shared/util';

const MAX_LABELS_TOTAL_LENGTH = 15;

/**
 * A component for displaying a list of test plans.
 */
@Component({
  standalone: false,
  selector: 'test-plan-list',
  styleUrls: ['test_plan_list.css'],
  templateUrl: './test_plan_list.ng.html',
})
export class TestPlanList implements OnInit, OnDestroy {
  readonly OverflowListType = OverflowListType;

  @Input()
  displayColumns =
      ['name', 'next_run_time', 'last_run_info', 'labels', 'actions'];

  isLoading = false;
  dataSource = new MatTableDataSource<TestPlan>();

  @ViewChild(MatTable, {static: false}) table!: MatTable<{}>;

  private readonly destroy = new ReplaySubject<void>();

  private readonly notifier = inject(Notifier);
  private readonly mttClient = inject(MttClient);
  private readonly router = inject(Router);
  private readonly liveAnnouncer = inject(LiveAnnouncer);

  ngOnInit() {
    this.load();
  }

  ngOnDestroy() {
    this.destroy.next();
    this.liveAnnouncer.clear();
  }

  load() {
    this.isLoading = true;
    this.liveAnnouncer.announce('Loading', 'polite');

    this.mttClient.getTestPlans()
        .pipe(
            takeUntil(this.destroy),
            finalize(() => {
              this.isLoading = false;
            }),
            )
        .subscribe(
            (result) => {
              this.dataSource.data = result.test_plans || [];
              this.liveAnnouncer.announce('Test plans loaded', 'assertive');
            },
            (error) => {
              this.notifier.showError(
                  'Failed to load test plan list.',
                  buildApiErrorMessage(error));
            },
        );
  }

  runTestPlan(testPlan: TestPlan) {
    if (!testPlan.id) {
      this.notifier.showError(`No ID was found in test plan ${testPlan.name}`);
      return;
    }
    this.mttClient.runTestPlan(testPlan.id)
        .subscribe(
            (result) => {
              this.notifier.showMessage(`Test plan '${testPlan.name}' started`);
            },
            (error) => {
              this.notifier.showError(
                  `Failed to start test plan '${testPlan.name}'`,
                  buildApiErrorMessage(error));
            });
  }

  confirmDeleteTestPlan(testPlan: TestPlan) {
    this.notifier
        .confirm(
            `Do you really want to delete test plan '${testPlan.name}'?`,
            'Delete test plan')
        .subscribe(result => {
          if (!result) {
            return;
          }
          this.deleteTestPlan(testPlan);
        });
  }

  deleteTestPlan(testPlan: TestPlan) {
    this.mttClient.deleteTestPlan(testPlan.id!)
        .subscribe(
            (result) => {
              this.notifier.showMessage(`Test plan '${testPlan.name}' deleted`);
              // Remove the test plan from this.testPlans.
              const index = this.dataSource.data.findIndex(o => o === testPlan);
              this.dataSource.data.splice(index, 1);
              this.table.renderRows();
            },
            (error) => {
              this.notifier.showError(
                  `Failed to delete '${testPlan.name}'.`,
                  buildApiErrorMessage(error));
            });
  }

  navigateToSuites(label: string) {
    this.router.navigate(
        ['/test_plans/edit_test_suites'], {queryParams: {'label': label}});
  }

  shouldShowExpand(labels?: string[]): boolean {
    if (!labels) {
      return false;
    }
    const totalLength = labels.reduce((acc, label) => acc + label.length, 0);
    return labels.length > 3 ||
        (labels.length > 0 && totalLength > MAX_LABELS_TOTAL_LENGTH);
  }

  getPreviewLabels(labels?: string[]): string[] {
    if (!labels) {
      return [];
    }
    const previewLabels: string[] = [];
    let currentLength = 0;
    for (const label of labels) {
      if (currentLength + label.length > MAX_LABELS_TOTAL_LENGTH) {
        break;
      }
      previewLabels.push(label);
      currentLength += label.length;
      if (previewLabels.length >= 2) {
        break;
      }
    }
    return previewLabels;
  }
}
