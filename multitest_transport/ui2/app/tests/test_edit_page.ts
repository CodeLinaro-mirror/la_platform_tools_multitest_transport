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

import {AfterViewInit, Component, OnInit, QueryList, ViewChild, ViewChildren} from '@angular/core';
import {MatButton} from '@angular/material/button';
import {ActivatedRoute, Router} from '@angular/router';
import {first} from 'rxjs/operators';

import {MttClient} from '../services/mtt_client';
import {BuildChannel, initTest, Test, TestResourceType, TestRunParameters} from '../services/mtt_models';
import {Notifier} from '../services/notifier';
import {FormChangeTracker} from '../shared/can_deactivate';
import {APPLICATION_NAME} from '../shared/shared_module';
import {buildApiErrorMessage} from '../shared/util';

/**
 * Form for creating a new test
 */
@Component({
  standalone: false,
  selector: 'test-edit-page',
  styleUrls: ['test_edit_page.css'],
  templateUrl: './test_edit_page.ng.html',
})
export class TestEditPage extends FormChangeTracker implements OnInit,
                                                               AfterViewInit {
  @ViewChild('backButton', {static: false}) backButton?: MatButton;
  @ViewChildren(FormChangeTracker)
  declare trackers: QueryList<FormChangeTracker>;

  data: Partial<Test> = initTest();
  outputFilePatterns: Partial<string[]> = [];
  uploadFilePattern: Partial<string[]> = [];
  setupScripts: Partial<string[]> = [];
  defaultTestRunParameters: Partial<TestRunParameters> = {};

  editMode = false;
  buildChannels: BuildChannel[] = [];
  title!: string;

  constructor(
      private readonly mttClient: MttClient,
      private readonly notifier: Notifier,
      private readonly route: ActivatedRoute, private readonly router: Router) {
    super();
  }

  ngOnInit() {
    this.title = `${APPLICATION_NAME}: Individual Tests`;
    this.route.params.pipe(first()).subscribe(params => {
      if (params['id']) {
        this.editMode = true;
        this.loadTest(params['id']);
      }
      if (params['copy_id']) {
        this.loadTest(params['copy_id']);
      }
    });
    this.loadBuildChannels();
  }

  ngAfterViewInit() {
    this.backButton!.focus();
  }

  loadTest(id: string) {
    this.mttClient.getTest(id).pipe(first()).subscribe(
        result => {
          this.data = result;
          this.setupScripts = result.setup_scripts || [];
          this.outputFilePatterns = result.output_file_patterns || [];
          this.uploadFilePattern = result.upload_file_patterns || [];
          this.data.env_vars = result.env_vars || [];
          this.data.test_resource_defs = result.test_resource_defs || [];
          this.data.jvm_options = result.jvm_options || [];
          this.data.java_properties = result.java_properties || [];
          this.data.build_attributes = result.build_attributes || [];
          this.defaultTestRunParameters =
              result.default_test_run_parameters || {};
          if (!this.editMode) {
            delete this.data.id;
            this.data.name = `${this.data.name} (copy)`;
          }
        },
        error => {
          this.notifier.showError(
              `Failed to load test '${id}'.`, buildApiErrorMessage(error));
        },
    );
  }

  loadBuildChannels() {
    this.mttClient.getBuildChannels().pipe(first()).subscribe(
        result => {
          this.buildChannels = result.build_channels || [];
        },
        error => {
          this.notifier.showError(
              'Failed to load build channels.', buildApiErrorMessage(error));
        },
    );
  }

  onAddEnvironmentVariable() {
    this.data.env_vars!.push({name: ''});
  }

  onAddOutputFilePattern() {
    this.outputFilePatterns.push(undefined);
  }

  onAddUploadFilePattern() {
    this.uploadFilePattern.push(undefined);
  }

  onAddJvmOption() {
    this.data.jvm_options!.push('');
  }

  onAddJavaProperty() {
    this.data.java_properties!.push({name: ''});
  }

  onAddBuildAttribute() {
    this.data.build_attributes!.push({name: ''});
  }

  onAddScript() {
    this.setupScripts.push(undefined);
  }

  onAddTestResourceDef() {
    this.data.test_resource_defs!.push({
      name: '',
      test_resource_type: TestResourceType.UNKNOWN,
    });
  }

  onRemoveEnvironmentVariable(i: number) {
    this.data.env_vars!.splice(i, 1);
  }

  onRemoveOutputFilePattern(i: number) {
    this.outputFilePatterns.splice(i, 1);
  }

  onRemoveUploadFilePattern(i: number) {
    this.uploadFilePattern.splice(i, 1);
  }

  onRemoveJvmOption(i: number) {
    this.data.jvm_options!.splice(i, 1);
  }

  onRemoveJavaProperty(i: number) {
    this.data.java_properties!.splice(i, 1);
  }

  onRemoveBuildAttribute(i: number) {
    this.data.build_attributes!.splice(i, 1);
  }

  onRemoveScript(i: number) {
    this.setupScripts.splice(i, 1);
  }

  onRemoveTestResourceDef(i: number) {
    this.data.test_resource_defs!.splice(i, 1);
  }

  back() {
    this.router.navigate(['tests']);
  }

  /**
   * Validate the form
   * return boolean. true if no error, false otherwise.
   */
  validate(): boolean {
    this.invalidInputs = this.getInvalidInputs();
    for (const tracker of this.trackers) {
      this.invalidInputs.push(...tracker.getInvalidInputs());
    }
    return !this.invalidInputs.length;
  }

  onSubmit() {
    if (!this.validate()) {
      return;
    }
    const resultTest: Test = {...this.data} as Test;
    resultTest.output_file_patterns =
        this.outputFilePatterns.filter(item => item !== undefined) as string[];
    resultTest.upload_file_patterns =
        this.uploadFilePattern.filter(item => item !== undefined) as string[];
    resultTest.setup_scripts =
        this.setupScripts.filter(item => item !== undefined) as string[];
    resultTest.default_test_run_parameters = this.defaultTestRunParameters;
    if (this.editMode) {
      this.mttClient.updateTest(resultTest.id!, resultTest)
          .pipe(first())
          .subscribe(
              result => {
                // Reset form state, because we prevent dirty forms from
                // navigating away
                super.resetForm();
                this.back();
                this.notifier.showMessage(`Test '${this.data.name}' updated`);
              },
              error => {
                this.notifier.showError(
                    `Failed to update test '${this.data.name}'.`,
                    buildApiErrorMessage(error));
              },
          );
    } else {
      this.mttClient.createTest(resultTest)
          .pipe(first())
          .subscribe(
              result => {
                // Reset form state, because we prevent dirty forms from
                // navigating away
                super.resetForm();
                this.back();
                this.notifier.showMessage(`Test '${this.data.name}' created`);
              },
              error => {
                this.notifier.showError(
                    `Failed to create test '${this.data.name}'.`,
                    buildApiErrorMessage(error));
              },
          );
    }
  }
}
