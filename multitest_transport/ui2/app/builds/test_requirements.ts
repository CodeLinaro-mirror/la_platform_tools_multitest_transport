
/**
 * Copyright 2024 Google LLC
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
import {Component, EventEmitter, Input, OnDestroy, OnInit, Output} from '@angular/core';
import {MatDialog} from '@angular/material/dialog';
import {MatTableDataSource} from '@angular/material/table';
import {ReplaySubject} from 'rxjs';
import {takeUntil} from 'rxjs/operators';

import {MttClient} from '../services/mtt_client';
import {initTestRunConfig, isFinalTestRunState, NewTestRunRequest, RequiredReport, Test, TestRunConfig} from '../services/mtt_models';
import {MttObjectMapService, newMttObjectMap} from '../services/mtt_object_map';
import {TestRunConfigEditor, TestRunConfigEditorData} from '../test_runs/test_run_config_editor';

/** Test requirement data to initialize a TestRunConfig. */
interface TestRequirementData {
  defaultTest?: Test;
  selectedTestPlan?: string;
}

/**
 * A component for displaying a list of test requirements for a build.
 */
@Component({
  selector: 'test-requirements',
  styleUrls: ['test_requirements.css'],
  templateUrl: './test_requirements.ng.html',
})
export class TestRequirements implements OnDestroy, OnInit {
  @Input()
  set dataSource(value: RequiredReport[]) {
    this.resetTestRequirementDataMap(value);
    this.tableDataSource.data = value;
  }

  @Output() readonly testRunRequested = new EventEmitter<void>();

  displayColumns =
      ['report_type', 'test_plan', 'test_run', 'test_run_status', 'run_test'];
  tableDataSource = new MatTableDataSource<RequiredReport>();

  testRequirementDataMap: {[reportId: string]: TestRequirementData} = {};

  mttObjectMap = newMttObjectMap();

  private readonly destroy = new ReplaySubject<void>();

  private static readonly REGEXP = /android.[\w]*\.(\d+)_(\d+)/i;

  constructor(
      private readonly mttObjectMapService: MttObjectMapService,
      private readonly matDialog: MatDialog,
      private readonly mttClient: MttClient,
  ) {}

  ngOnInit() {
    this.mttObjectMapService.getMttObjectMap().subscribe((res) => {
      this.mttObjectMap = res;
      for (const requiredReport of this.tableDataSource.data) {
        const testRequirementData =
            this.testRequirementDataMap[requiredReport.id];
        testRequirementData.defaultTest = this.getDefaultTest(requiredReport);
      }
    });
  }

  ngOnDestroy() {
    this.destroy.next();
    this.destroy.complete();
  }

  /**
   * Resets the test requirement data map.
   */
  resetTestRequirementDataMap(requiredReports: RequiredReport[]) {
    this.testRequirementDataMap = {};
    for (const requiredReport of requiredReports) {
      this.testRequirementDataMap[requiredReport.id] = {
        defaultTest: this.getDefaultTest(requiredReport),
        selectedTestPlan: this.getDefaultTestPlan(requiredReport),
      };
    }
  }

  /**
   * Gets the default test that is eligible to run for a required report.
   */
  getDefaultTest(requiredReport: RequiredReport): Test|undefined {
    let defaultTest = undefined;
    for (const test of Object.values(this.mttObjectMap.testMap)) {
      if (this.isTestEligibleForRun(test, requiredReport) &&
          this.greaterThan(test, defaultTest)) {
        defaultTest = test;
      }
    }
    return defaultTest;
  }

  /**
   * Whether the test is eligible to run for a required report.
   */
  isTestEligibleForRun(test: Test, requiredReport: RequiredReport): boolean {
    return test.id!.includes(`.${requiredReport.type.toLowerCase()}.`);
  }

  /**
   * Whether the suite version of the left test is greater than right.
   * Returns true if right test is undefined.
   */
  greaterThan(left: Test, right: Test|undefined): boolean {
    if (right === undefined) {
      return true;
    }
    const leftMatch = TestRequirements.REGEXP.exec(left.id!);
    const leftMajorVersion = leftMatch ? Number(leftMatch[1]) : 0;
    const leftMinorVersion = leftMatch ? Number(leftMatch[2]) : 0;

    const rightMatch = TestRequirements.REGEXP.exec(right.id!);
    const rightMajorVersion = rightMatch ? Number(rightMatch[1]) : 0;
    const rightMinorVersion = rightMatch ? Number(rightMatch[2]) : 0;

    return (leftMajorVersion > rightMajorVersion) ||
        (leftMajorVersion === rightMajorVersion &&
         leftMinorVersion > rightMinorVersion);
  }

  /**
   * Gets the default test plan to run for a required report.
   */
  getDefaultTestPlan(requiredReport: RequiredReport): string|undefined {
    let defaultTestPlan = undefined;
    if (!requiredReport.test_plans) {
      return defaultTestPlan;
    }
    for (const testPlan of requiredReport.test_plans) {
      if (defaultTestPlan === undefined || testPlan.includes('system')) {
        defaultTestPlan = testPlan;
      }
    }
    return defaultTestPlan;
  }

  /**
   * Whether the required report has qualified test plans.
   */
  hasTestPlans(requiredReport: RequiredReport): boolean {
    return requiredReport.test_plans !== undefined;
  }

  getTestRequirementData(requiredReport: RequiredReport): TestRequirementData {
    return this.testRequirementDataMap[requiredReport.id];
  }

  /**
   * Whether the run button is disabled for a required report.
   */
  runButtonDisabled(requiredReport: RequiredReport): boolean {
    const testRequirementData = this.testRequirementDataMap[requiredReport.id];
    if (!testRequirementData.defaultTest) {
      return true;
    }
    if (!requiredReport.test_run_state) {
      return false;
    }
    return !isFinalTestRunState(requiredReport.test_run_state);
  }

  /**
   * Opens the test run config editor to set up a test run for a required
   * report.
   */
  openTestRunConfigEditor(requiredReport: RequiredReport): void {
    const testRequirementData = this.testRequirementDataMap[requiredReport.id];
    const testRunConfig = initTestRunConfig(
        testRequirementData.defaultTest, testRequirementData.selectedTestPlan);
    const testRunConfigEditorData: TestRunConfigEditorData = {
      editMode: false,
      testRunConfig,
      testPlanToOverride: testRequirementData.selectedTestPlan,
    };

    const dialogRef = this.matDialog.open(TestRunConfigEditor, {
      panelClass: 'test-run-config-editor-dialog',
      data: testRunConfigEditorData,
    });

    dialogRef.componentInstance.configSubmitted
        .pipe(takeUntil(dialogRef.afterClosed()))
        .subscribe((newConfig: TestRunConfig) => {
          const newTestRunRequest: NewTestRunRequest = {
            labels: ['test requirement', requiredReport.id],
            test_run_config: {...newConfig} as TestRunConfig,
            required_report_id: requiredReport.id,
          };
          return this.mttClient.createNewTestRunRequest(newTestRunRequest)
              .pipe(takeUntil(this.destroy))
              .subscribe(() => {
                this.testRunRequested.emit();
              });
        });
  }
}
