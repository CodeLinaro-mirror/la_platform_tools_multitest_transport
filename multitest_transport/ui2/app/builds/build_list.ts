
/**
 * Copyright 2023 Google LLC
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
import {Component, Input, OnDestroy, OnInit} from '@angular/core';
import {MatTableDataSource} from '@angular/material/table';
import {ReplaySubject} from 'rxjs';
import {finalize, takeUntil} from 'rxjs/operators';

import {MttClient} from '../services/mtt_client';
import {Build} from '../services/mtt_models';
import {Notifier} from '../services/notifier';
import {OverflowListType} from '../shared/overflow_list';
import {buildApiErrorMessage} from '../shared/util';

/**
 * A component for displaying a list of builds.
 */
@Component({
  selector: 'build-list',
  styleUrls: ['build_list.css'],
  templateUrl: './build_list.ng.html',
})
export class BuildList implements OnInit, OnDestroy {
  readonly OverflowListType = OverflowListType;

  private readonly destroy = new ReplaySubject<void>();

  @Input()
  displayColumns =
      ['select', 'name', 'source', 'size', 'labels', 'create_time'];

  isLoading = false;
  dataSource = new MatTableDataSource<Build>();
  selection = new SelectionModel<Build>(
      /*allow multi select*/ true, []);

  constructor(
      private readonly notifier: Notifier,
      private readonly mttClient: MttClient,
      private readonly liveAnnouncer: LiveAnnouncer) {}

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
    this.selection.clear();

    this.mttClient.builds.list()
        .pipe(
            takeUntil(this.destroy),
            finalize(() => {
              this.isLoading = false;
            }),
            )
        .subscribe(
            (result) => {
              this.dataSource.data = result.builds || [];
              this.liveAnnouncer.announce('Builds loaded', 'assertive');
            },
            (error) => {
              this.notifier.showError(
                  'Failed to load build list.', buildApiErrorMessage(error));
            },
        );
  }

  /**
   * Whether the number of selected elements matches the total number of rows.
   */
  isAllSelected() {
    return this.selection.selected.length === this.dataSource.data.length;
  }

  /**
   * Selects all rows if they are not all selected; otherwise clear selection.
   */
  toggleSelection() {
    if (this.isAllSelected()) {
      this.selection.clear();
      return;
    }

    for (const row of this.dataSource.data) {
      this.selection.select(row);
    }
  }

  /**
   * Selects all rows if they are not all selected; otherwise clear selection.
   */
  deleteSelectedBuilds() {
    this.notifier
        .confirm('Do you really want to delete these builds?', 'Delete Builds')
        .subscribe(result => {
          if (!result) {
            return;
          }
          this.isLoading = true;
          this.mttClient.builds
              .delete(this.selection.selected.map(build => build.id!))
              .pipe(
                  takeUntil(this.destroy),
                  finalize(() => {
                    this.load();
                  }),
                  )
              .subscribe(
                  () => {
                    this.notifier.showMessage('Builds deleted.');
                  },
                  (error) => {
                    this.notifier.showError(
                        'Failed to delete builds.',
                        buildApiErrorMessage(error));
                  });
        });
  }
}
