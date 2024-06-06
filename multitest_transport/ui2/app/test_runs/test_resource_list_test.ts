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

import {DebugElement} from '@angular/core';
import {ComponentFixture, TestBed} from '@angular/core/testing';
import {NoopAnimationsModule} from '@angular/platform-browser/animations';

import {FileService} from '../services/file_service';
import {Test, TestResourceObj, TestRun, TestRunState} from '../services/mtt_models';
import {getTextContent} from '../testing/jasmine_util';
import {newMockTest, newMockTestResourceObj, newMockTestRun} from '../testing/mtt_mocks';
import {TestResourceList} from './test_resource_list';
import {TestRunsModule} from './test_runs_module';

describe('TestResourceList', () => {
  let testResourceList: TestResourceList;
  let testResourceListFixture: ComponentFixture<TestResourceList>;
  let fs: jasmine.SpyObj<FileService>;
  let el: DebugElement;

  let test: Test;
  let testRun: TestRun;
  let testResourceObj: TestResourceObj;

  beforeEach(() => {
    test = newMockTest();
    testResourceObj = newMockTestResourceObj();
    testRun = newMockTestRun(
        test, 'trid123', TestRunState.COMPLETED, [testResourceObj]);

    fs = jasmine.createSpyObj(['getFileOpenUrl']);
    fs.getFileOpenUrl.and.returnValue('open_url');

    TestBed.configureTestingModule({
      imports: [NoopAnimationsModule, TestRunsModule],
      providers: [
        {provide: FileService, useValue: fs},
      ],
    });
    testResourceListFixture = TestBed.createComponent(TestResourceList);
    testResourceList = testResourceListFixture.componentInstance;
    el = testResourceListFixture.debugElement;
    testResourceList.testRun = testRun;
    testResourceListFixture.detectChanges();
  });

  it('displays the table headers and data', () => {
    const textContent = getTextContent(el);
    expect(textContent).toContain('Name');
    expect(textContent).toContain('Source');
    expect(textContent).toContain('Link');

    expect(textContent).toContain(testResourceObj.name!);
    expect(textContent).toContain(testResourceObj.cache_url!);
    expect(textContent).toContain('Open');
  });
});
