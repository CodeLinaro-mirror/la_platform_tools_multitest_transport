/**
 * Copyright 2020 Google LLC
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

/**
 * Canonical representation of a filter operator containing all properties
 * necessary for display.
 */
export class TimeFilterOperator {
  constructor(
      readonly description: string,
      readonly shorthand?: string,
      readonly urlId?: string,
  ) {}

  static readonly ALL = new TimeFilterOperator('All');

  /**
   * The backend takes timestamp to filter data, greater than a time in filter
   * data means less then a timestamp.
   */
  static readonly GREATER_THAN =
      new TimeFilterOperator('Greater than', undefined, 'LESS_THAN');

  /**
   * The backend takes timestamp to filter data, within a time in filter data
   * means greater then a timestamp.
   */
  static readonly WITHIN =
      new TimeFilterOperator('Within', undefined, 'GREATER_THAN_OR_EQUAL');

  /** All defined display operators. */
  static readonly OPERATORS: TimeFilterOperator[] = [
    TimeFilterOperator.ALL,
    TimeFilterOperator.GREATER_THAN,
    TimeFilterOperator.WITHIN,
  ];
}

/**
 * A general representation of a time filter which contains the information
 * necessary to render.
 */
export interface TimeFilterEvent {
  filterOperator: TimeFilterOperator;
  hours?: number;
  timestamp?: Date;
}

/**
 * Common component for choosing a filter using a select for filter operator
 * and manual input for value. Emits a TimeFilterEvent representing the chosen
 * filter.
 */
@Component({
  selector: 'time-input-filter',
  styleUrls: ['time_input_filter.css'],
  templateUrl: './time_input_filter.ng.html',
})
export class TimeInputFilter {
  @Input() label = '';
  @Input() suffix = 'Hours';
  @Input() appearance = 'fill';
  @Input() operatorWidth = '135px';
  @Input() numberInputWidth = '100px';
  @Input() number = 0;
  @Input() maximumNumber = 99;
  @Input() operator = TimeFilterOperator.ALL;

  @Output() readonly timeFilterChange = new EventEmitter<TimeFilterEvent>();

  operators = TimeFilterOperator.OPERATORS;

  getOffsetTimestamp(): Date {
    const date = new Date();
    date.setHours(date.getHours() - this.number);
    return date;
  }

  isAllOptionSelected(): boolean {
    return this.operator.description === TimeFilterOperator.ALL.description;
  }

  validateInput(): boolean {
    if (!this.isAllOptionSelected() && this.number <= 0) {
      return false;
    }
    return true;
  }

  filterChange() {
    if (!this.validateInput()) {
      return;
    }
    const timeFilter = {
      filterOperator: this.operator,
      hours: this.isAllOptionSelected() ? undefined : this.number,
      timestamp: this.isAllOptionSelected() ? undefined :
                                              this.getOffsetTimestamp(),
    };
    this.timeFilterChange.emit(timeFilter);
  }
}
