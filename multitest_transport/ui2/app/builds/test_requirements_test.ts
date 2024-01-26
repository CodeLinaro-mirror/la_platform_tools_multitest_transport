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

import {DebugElement} from '@angular/core';
import {ComponentFixture, TestBed} from '@angular/core/testing';
import {NoopAnimationsModule} from '@angular/platform-browser/animations';

import {getTextContent} from '../testing/jasmine_util';
import {newMockBuild} from '../testing/mtt_mocks';

import {BuildsModule} from './builds_module';
import {TestRequirements} from './test_requirements';

describe('TestRequirements', () => {
  let testRequirements: TestRequirements;
  let testRequirementsFixture: ComponentFixture<TestRequirements>;
  let el: DebugElement;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [BuildsModule, NoopAnimationsModule],
    });

    testRequirementsFixture = TestBed.createComponent(TestRequirements);
    testRequirementsFixture.detectChanges();
    el = testRequirementsFixture.debugElement;
    testRequirements = testRequirementsFixture.componentInstance;
  });

  it('gets initialized', () => {
    expect(testRequirements).toBeTruthy();
  });

  it('should display test requirements correctly', () => {
    const requiredReports = newMockBuild().required_reports;
    testRequirements.dataSource = requiredReports;
    testRequirementsFixture.detectChanges();
    const textContent = getTextContent(el);
    for (const requiredReport of requiredReports) {
      expect(textContent).toContain(requiredReport.type);
      if (requiredReport.test_plans) {
        for (const testPlan of requiredReport.test_plans) {
          expect(textContent).toContain(testPlan);
        }
      }
    }
  });
});
