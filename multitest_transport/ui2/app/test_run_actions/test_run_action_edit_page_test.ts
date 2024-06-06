/**
 * Copyright 2022 Google LLC
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
import {ActivatedRoute, RouterModule} from '@angular/router';
import {of as observableOf} from 'rxjs';

import {MttClient, TestRunActionClient} from '../services/mtt_client';
import {getEl, getTextContent} from '../testing/jasmine_util';

import {TestRunActionEditPage} from './test_run_action_edit_page';
import {TestRunActionsModule} from './test_run_actions_module';

describe('TestRunActionEditPage', () => {
  let testRunActionEditPage: TestRunActionEditPage;
  let testRunActionEditPageFixture: ComponentFixture<TestRunActionEditPage>;
  let testRunActionClient: jasmine.SpyObj<TestRunActionClient>;
  let el: DebugElement;

  beforeEach(() => {
    testRunActionClient = jasmine.createSpyObj(['get', 'listTestRunHooks']);
    testRunActionClient.get.and.returnValue(observableOf({
      id: 'id',
      name: 'test run action',
      hook_class_name: 'hook class',
    }));
    testRunActionClient.listTestRunHooks.and.returnValue(observableOf({
      test_run_hooks: [
        {
          name: 'hook class 1',
        },
        {
          name: 'hook class 2',
          option_defs: [
            {
              name: 'option1',
              value_type: 'str',
            },
            {
              name: 'option2',
              value_type: 'str',
              default: 'default',
            },
          ]
        },
      ],
    }));

    TestBed.configureTestingModule({
      imports: [NoopAnimationsModule, RouterModule, TestRunActionsModule],
      providers: [
        {
          provide: MttClient,
          useValue: {
            testRunActions: testRunActionClient,
          }
        },
        {
          provide: ActivatedRoute,
          useValue: {
            params: observableOf({'id': '123'}),
          },
        },
      ],
    });
    testRunActionEditPageFixture =
        TestBed.createComponent(TestRunActionEditPage);
    el = testRunActionEditPageFixture.debugElement;
    testRunActionEditPageFixture.detectChanges();
    testRunActionEditPage = testRunActionEditPageFixture.componentInstance;
  });

  it('initializes a component', () => {
    expect(testRunActionEditPage).toBeTruthy();
  });

  it('calls API correctly', () => {
    expect(testRunActionClient.get).toHaveBeenCalled();
    expect(testRunActionClient.listTestRunHooks).toHaveBeenCalled();
  });

  it('displays texts correctly', () => {
    const textContent = getTextContent(el);
    expect(textContent).toContain('Edit Test Run Action');
    expect(textContent).toContain('Test Run Action Information');
    expect(textContent).toContain('Name');
    expect(textContent).toContain('Description');
    expect(textContent).toContain('Hook Class Name');
    expect(textContent).toContain('Test Run Phases');
    expect(textContent).toContain('Options');
    expect(textContent).toContain('TradeFed Result Reporters');
  });

  it('handles option events', () => {
    expect(testRunActionEditPage.data.options).toBeDefined();
    testRunActionEditPage.onAddOption();
    testRunActionEditPage.onAddOption();
    expect(testRunActionEditPage.data.options!.length).toBe(2);

    const first = testRunActionEditPage.data.options![0];
    testRunActionEditPage.onRemoveOption(1);
    expect(testRunActionEditPage.data.options!.length).toBe(1);
    expect(testRunActionEditPage.data.options![0]).toBe(first);
  });

  it('handles result reporter events', () => {
    expect(testRunActionEditPage.data.tradefed_result_reporters).toBeDefined();
    testRunActionEditPage.onAddResultReporter();
    testRunActionEditPage.onAddResultReporter();
    expect(testRunActionEditPage.data.tradefed_result_reporters!.length)
        .toBe(2);

    const first = testRunActionEditPage.data.tradefed_result_reporters![0];
    testRunActionEditPage.onDeleteResultReporter(1);
    expect(testRunActionEditPage.data.tradefed_result_reporters!.length)
        .toBe(1);
    expect(testRunActionEditPage.data.tradefed_result_reporters![0])
        .toBe(first);
  });

  it('handles test run hook events', () => {
    testRunActionEditPage.onAddOption();
    expect(testRunActionEditPage.data.options!.length).toBe(1);
    testRunActionEditPage.onSelectTestRunHook('hook class 1');
    expect(testRunActionEditPage.data.options!.length).toBe(0);

    testRunActionEditPage.onSelectTestRunHook('hook class 2');
    expect(testRunActionEditPage.data.options!.length).toBe(2);
    expect(testRunActionEditPage.data.options).toEqual([
      {name: 'option1', value: ''},
      {name: 'option2', value: 'default'},
    ]);
  });

  describe('back button', () => {
    it('should display correct aria-label and tooltip', () => {
      const backButton = getEl(el, '#back-button');
      expect(backButton).toBeTruthy();
      expect(backButton.getAttribute('aria-label'))
          .toBe('Return to settings page');
      expect(backButton.getAttribute('mattooltip'))
          .toBe('Return to settings page');
    });
  });
});
