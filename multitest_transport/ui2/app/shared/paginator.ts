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

import {Component, EventEmitter, Input, Output} from '@angular/core';

/** Default page size. */
export const DEFAULT_PAGE_SIZE = 10;

/**
 * Simple paginator for use with server-side paging.
 *
 * Instead of relying on page index and total number of elements when enabling
 * buttons and broadcasting events, it allows callers to manually enable and
 * disable buttons and explicitly listen for previous or next page events.
 */
@Component({
  standalone: false,
  selector: 'paginator',
  styles: [`
    :host {
      align-items: center;
      color: rgba(0, 0, 0, .54);
      display: flex;
      font-size: 12px;
      justify-content: flex-end;
      min-height: 56px;
      padding: 0 8px;
    }

    .page-size-label {
      margin: 0 4px;
    }

    .page-size-select {
      margin: 6px 4px 0;
      width: 108px;
    }

   ::ng-deep .page-size-select .mat-form-field-infix {
      height: 20px;
    }

    mat-icon {
      font-size: 28px;
    }

    button[disabled] {
      opacity: .6;
    }

    .page-index {
      margin: 0 4px;
    }
  `],
  template: `
    <span class="page-index" *ngIf="showPageIndex">Page: {{pageIndex}},</span>
    <span class="page-size-label">Items per page:</span>
    <mat-form-field *ngIf="pageSizeOptions.length > 1"
                    class="page-size-select">
      <mat-select [value]="pageSize"
                  (selectionChange)="changePageSize($event.value)">
        <mat-option *ngFor="let option of pageSizeOptions"
                    [value]="option">{{option}}</mat-option>
      </mat-select>
    </mat-form-field>

    <button mat-icon-button class="previous-page"
            (click)="previousPage()"
            [disabled]="!hasPrevious"
            aria-label="Previous page"
            matTooltip="Previous page" [matTooltipDisabled]="!hasPrevious"
            matTooltipPosition="above">
      <mat-icon color="primary">chevron_left</mat-icon>
    </button>
    <button mat-icon-button class="next-page"
            (click)="nextPage()" [disabled]="!hasNext"
            matTooltip="Next page"
            aria-label="Next page"
            [matTooltipDisabled]="!hasNext"
            matTooltipPosition="above">
      <mat-icon color="primary">chevron_right</mat-icon>
    </button>
  `,
})
export class Paginator {
  @Input() hasNext = false;
  @Input() hasPrevious = false;
  @Input() pageSizeOptions: number[] = [];
  @Input() pageSize = DEFAULT_PAGE_SIZE;
  @Input() showPageIndex = false;

  @Output() readonly sizeChange = new EventEmitter<number>();
  @Output() readonly previous = new EventEmitter<void>();
  @Output() readonly next = new EventEmitter<void>();

  pageIndex = 1;

  changePageSize(size: number) {
    this.resetPageIndex();
    this.pageSize = size;
    this.sizeChange.emit(size);
  }

  nextPage() {
    this.pageIndex++;
    this.next.emit();
  }

  previousPage() {
    this.pageIndex--;
    this.previous.emit();
  }

  resetPageIndex() {
    this.pageIndex = 1;
  }
}
