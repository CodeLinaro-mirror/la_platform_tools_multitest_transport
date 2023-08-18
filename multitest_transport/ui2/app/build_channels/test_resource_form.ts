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

import {Component, EventEmitter, Input, OnInit, Output} from '@angular/core';
import {MatDialog} from '@angular/material/dialog';
import {Observable, of} from 'rxjs';
import {takeUntil} from 'rxjs/operators';

import {MttClient} from '../services/mtt_client';
import {BuildChannel, BuildItem, TestResourceDef, TestResourceObj, TestResourceType} from '../services/mtt_models';
import {FormChangeTracker} from '../shared/can_deactivate';
import {arrayToString, assertRequiredInput} from '../shared/util';

import {BuildPicker, BuildPickerData, BuildPickerMode} from './build_picker';

/** Class of test resources being used in this form */
export enum TestResourceClassType {
  TEST_RESOURCE_DEF = 'TestResourceDef',
  TEST_RESOURCE_OBJ = 'TestResourceObj',
}

/**
 * Form for Test Resource Definition
 */
@Component({
  selector: 'test-resource-form',
  styleUrls: ['test_resource_form.css'],
  templateUrl: './test_resource_form.ng.html',
  providers: [{provide: FormChangeTracker, useExisting: TestResourceForm}]
})
export class TestResourceForm extends FormChangeTracker implements OnInit {
  readonly TEST_RESOURCE_TYPES = Object.values(TestResourceType);

  @Input() data!: TestResourceObj[]|TestResourceDef[];
  @Input() buildChannels!: BuildChannel[];
  @Input() testResourceClassType!: TestResourceClassType;
  @Input() canAdd = true;
  @Input() canDelete = true;

  @Output() readonly addTestResource = new EventEmitter();
  @Output() readonly removeTestResource = new EventEmitter<number>();

  // Whenever an event fired such as add or remove, it will set this value to
  // true
  override hasContentChanged = false;
  buildItemByUrl: {[url: string]: Observable<BuildItem|null>} = {};
  arrayToString = arrayToString;

  ngOnInit() {
    assertRequiredInput(this.data, 'data', 'test-resource-form');
    assertRequiredInput(
        this.testResourceClassType, 'testResourceClassType',
        'test-resource-form');
    assertRequiredInput(
        this.buildChannels, 'buildChannels', 'test-resource-form');
  }

  constructor(
      private readonly mttClient: MttClient,
      private readonly dialog: MatDialog) {
    super();
  }

  onDecompressFileNameChange(value: string, testResource: TestResourceDef) {
    if (!testResource.params) {
      testResource.params = {};
    }
    testResource.params.decompress_files = value ? value.split('\n') : [];
  }

  openBuildPicker(testResource: TestResourceObj|TestResourceDef) {
    const dialogRef =
        this.dialog.open<BuildPicker, BuildPickerData, string>(BuildPicker, {
          width: '800px',
          maxHeight: '100vh',
          panelClass: 'build-picker-container',
          data: {
            buildChannels: this.buildChannels,
            mode: BuildPickerMode.SELECT,
            resourceUrl: this.getUrl(testResource),
          }
        });

    // Update build channels when a channel is authorized in the dialog.
    dialogRef.componentInstance.buildChannelsChange
        .pipe(takeUntil(dialogRef.afterClosed()))
        .subscribe(buildChannels => {
          this.buildChannels = buildChannels;
        });

    dialogRef.afterClosed().subscribe(resourceUrl => {
      if (resourceUrl) {
        this.setUrl(testResource, resourceUrl);
      }
    });
  }

  private getUrl(testResource: TestResourceDef|TestResourceObj): string
      |undefined {
    if (this.isDef(testResource)) {
      return testResource.default_download_url;
    } else {
      return testResource.url;
    }
  }

  private setUrl(testResource: TestResourceDef|TestResourceObj, url: string) {
    if (this.isDef(testResource)) {
      testResource.default_download_url = url;
    } else {
      testResource.url = url;
    }
  }

  isDef(testResource: TestResourceDef|
        TestResourceObj): testResource is TestResourceDef {
    return this.testResourceClassType ===
        TestResourceClassType.TEST_RESOURCE_DEF;
  }

  getBuildItem(testResource: TestResourceDef|
               TestResourceObj): Observable<BuildItem|null> {
    const url = this.getUrl(testResource);
    if (!url) {
      return of(null);
    }
    if (!(url in this.buildItemByUrl)) {
      this.buildItemByUrl[url] = this.mttClient.lookupBuildItem(url);
    }
    return this.buildItemByUrl[url];
  }

  override isFormDirty(): boolean {
    return super.isFormDirty() || this.hasContentChanged;
  }

  override resetForm() {
    super.resetForm();
    this.hasContentChanged = false;
  }
}
