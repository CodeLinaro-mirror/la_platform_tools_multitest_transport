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

import {Component, EventEmitter, forwardRef, Input, OnChanges, Output, ChangeDetectionStrategy} from '@angular/core';
import {ControlValueAccessor, NG_VALUE_ACCESSOR} from '@angular/forms';

/** Schedule types. */
export enum ScheduleType {
  MANUAL = 'Manual',      // No cron expression (manually triggered)
  PERIODIC = 'Periodic',  // Simple cron expression
  CUSTOM = 'Custom'       // Complex cron expression
}

/** Simple period types. */
export enum PeriodicType {
  HOUR = 'Hour',    // Triggered once per hour
  DAY = 'Day',      // Triggered once per day
  WEEK = 'Week',    // Triggered once per week
  MONTH = 'Month',  // Triggered once per month
}

/** Week day names, indexed by their cron day-of-week value (0 = Sunday). */
const WEEK_DAYS = [
  'Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'
];

/** Cron day-of-week value for Monday. */
const MONDAY = 1;

/** Regular expressions corresponding to each periodic type. */
const PERIODIC_TYPE_REGEXPS = new Map<PeriodicType, RegExp>();
PERIODIC_TYPE_REGEXPS.set(
    PeriodicType.HOUR, /^([0-9]|[1-5][0-9])\s(\*\s){3}\*$/);
PERIODIC_TYPE_REGEXPS.set(
    PeriodicType.DAY,
    /^([0-9]|[1-5][0-9])\s([0-9]|1[0-9]|2[0-3])\s(\*\s){2}\*$/);
PERIODIC_TYPE_REGEXPS.set(
    PeriodicType.WEEK,
    /^([0-9]|[1-5][0-9])\s([0-9]|1[0-9]|2[0-3])\s(\*\s){2}[0-6]$/);
PERIODIC_TYPE_REGEXPS.set(
    PeriodicType.MONTH,
    /^([0-9]|[1-5][0-9])\s([0-9]|1[0-9]|2[0-3])\s([1-9]|[1-2][0-9]|3[0-1])\s\*\s\*$/);

/** Find periodic type which matches a cron expression. */
export function getPeriodicType(cron: string): undefined|PeriodicType {
  for (const [type, regex] of PERIODIC_TYPE_REGEXPS.entries()) {
    if (regex.test(cron)) {
      return type;
    }
  }
  return undefined;
}

/**
 * Converts a number input value to an integer within [min, max]. Empty or
 * non-numeric values (e.g. a cleared number input) are replaced by fallback.
 */
function clampNumber(
    value: unknown, min: number, max: number, fallback: number): number {
  return Math.min(max, Math.max(min, Math.round(Number(value)) || fallback));
}

/** Returns the client-side local timezone. */
export function getLocalTimezone(): string {
  return Intl.DateTimeFormat().resolvedOptions().timeZone;
}

/** Manages scheduling times using simple fields or cron expressions. */
@Component({
  changeDetection: ChangeDetectionStrategy.Eager,standalone: false,
  selector: 'schedule-time-form',
  styleUrls: ['schedule_time_form.css'],
  templateUrl: './schedule_time_form.ng.html',
  providers: [{
    provide: NG_VALUE_ACCESSOR,
    useExisting: forwardRef(() => ScheduleTimeForm),
    multi: true
  }]
})
export class ScheduleTimeForm implements ControlValueAccessor, OnChanges {
  readonly ScheduleTimeType = ScheduleType;
  readonly PeriodicTimeType = PeriodicType;
  readonly scheduleOptions = Object.values(ScheduleType);
  readonly periodicOptions = Object.values(PeriodicType);
  readonly weekDayOptions = WEEK_DAYS;

  /**
   * If true, an additional "Keep Original" schedule option is shown. It is
   * represented by an empty schedule type and a null cron expression, and
   * allows callers (e.g. batch editors) to leave existing schedules untouched.
   */
  @Input() allowKeepOriginal = false;

  /**
   * Emitted whenever the user selects a schedule type, before the resulting
   * cron expression is propagated to the model. Not emitted for programmatic
   * changes (e.g. writeValue).
   */
  @Output() readonly scheduleTypeChange = new EventEmitter<ScheduleType|''>();

  // Managed model and change callback (to handle external changes separately)
  cronExpression: string|null = null;
  onChange = (value: string|null) => {};

  // Timezone value and options
  @Input() timezone = getLocalTimezone();
  @Output() readonly timezoneChange = new EventEmitter<string>();
  /** Additional timezones to offer (e.g. timezones already in use). */
  @Input() extraTimezones: string[] = [];
  timezoneOptions: string[] = [];

  // Selected parameters
  selectedScheduleType: ScheduleType|'' = ScheduleType.MANUAL;
  selectedPeriodicType = PeriodicType.HOUR;
  selectedMonthDay = 1;
  selectedWeekDay = MONDAY;
  selectedHour = 0;
  selectedMinute = 0;

  /** Registers a change callback. */
  registerOnChange(fn: (value: string|null) => void): void {
    this.onChange = fn;
  }

  /** Unused ControlValueAccessor method. */
  registerOnTouched(fn: () => void): void {}

  /** Re-initializes the managed cron expression. */
  writeValue(value: string|null|undefined): void {
    this.cronExpression = value ?? null;
    if (!this.cronExpression) {
      if (this.allowKeepOriginal && value == null) {
        // No value provided, keep the original schedules
        this.selectedScheduleType = '';
        return;
      }
      // No expression, will have to be triggered manually
      this.selectedScheduleType = ScheduleType.MANUAL;
      return;
    }
    this.selectedScheduleType = ScheduleType.CUSTOM;
    const periodicType = getPeriodicType(this.cronExpression);
    if (periodicType) {
      // Matches a periodic type, initialize periodic parameters
      this.selectedScheduleType = ScheduleType.PERIODIC;
      this.selectedPeriodicType = periodicType;
      this.setPeriodicParameters(periodicType, this.cronExpression);
    }
  }

  /** Recalculates possible timezone options when the timezone changes. */
  ngOnChanges(): void {
    const localTimezone = getLocalTimezone();
    this.timezone = this.timezone || localTimezone;
    // UTC, local and current timezones first, followed by sorted extras
    const timezones = [
      'UTC', localTimezone, this.timezone, ...[...this.extraTimezones].sort()
    ].filter(tz => !!tz);
    this.timezoneOptions = [...new Set(timezones)];
  }

  /** Change schedule type and update cron expression. */
  changeScheduleType(scheduleType: ScheduleType|'') {
    this.scheduleTypeChange.emit(scheduleType);
    switch (scheduleType) {
      case '': {
        // Keep original
        this.onChange(null);
        break;
      }
      case ScheduleType.MANUAL: {
        this.onChange('');
        break;
      }
      case ScheduleType.PERIODIC: {
        const cron = this.cronExpression || '';
        const periodicType = getPeriodicType(cron);
        if (periodicType) {
          this.setPeriodicParameters(periodicType, cron);
        }
        this.updatePeriodicCron();
        break;
      }
      case ScheduleType.CUSTOM: {
        this.onChange(this.cronExpression || '');
        break;
      }
      default: {
        throw new Error(`unexpected value ${scheduleType}!`);
      }
    }
  }

  /** Update cron expression using current periodic parameters. */
  updatePeriodicCron() {
    // Normalize the inputs so that they show the values being used
    this.selectedMinute = clampNumber(this.selectedMinute, 0, 59, 0);
    this.selectedHour = clampNumber(this.selectedHour, 0, 23, 0);
    this.selectedMonthDay = clampNumber(this.selectedMonthDay, 1, 31, 1);
    const cronArray: string[] = Array.from<string>({length: 5}).fill('*');
    switch (this.selectedPeriodicType) {
      case PeriodicType.HOUR: {
        cronArray[0] = String(this.selectedMinute);
        break;
      }
      case PeriodicType.DAY: {
        cronArray[0] = String(this.selectedMinute);
        cronArray[1] = String(this.selectedHour);
        break;
      }
      case PeriodicType.WEEK: {
        cronArray[0] = String(this.selectedMinute);
        cronArray[1] = String(this.selectedHour);
        cronArray[4] = String(this.selectedWeekDay);
        break;
      }
      case PeriodicType.MONTH: {
        cronArray[0] = String(this.selectedMinute);
        cronArray[1] = String(this.selectedHour);
        cronArray[2] = String(this.selectedMonthDay);
        break;
      }
      default: {
        throw new Error(`unexpected value ${this.selectedPeriodicType}!`);
      }
    }

    this.cronExpression = cronArray.join(' ');
    this.onChange(this.cronExpression);
  }

  /** Set periodic parameters from a cron expression. */
  private setPeriodicParameters(type: PeriodicType, cron: string) {
    const cronArray: string[] = cron.split(' ');
    this.selectedPeriodicType = type;
    switch (this.selectedPeriodicType) {
      case PeriodicType.HOUR: {
        this.selectedMinute = Number(cronArray[0]) || 0;
        break;
      }
      case PeriodicType.DAY: {
        this.selectedMinute = Number(cronArray[0]) || 0;
        this.selectedHour = Number(cronArray[1]) || 0;
        break;
      }
      case PeriodicType.WEEK: {
        this.selectedMinute = Number(cronArray[0]) || 0;
        this.selectedHour = Number(cronArray[1]) || 0;
        this.selectedWeekDay = Number(cronArray[4]);
        break;
      }
      case PeriodicType.MONTH: {
        this.selectedMinute = Number(cronArray[0]) || 0;
        this.selectedHour = Number(cronArray[1]) || 0;
        this.selectedMonthDay = Number(cronArray[2]) || 1;
        break;
      }
      default: {
        throw new Error(`unexpected value ${this.selectedPeriodicType}!`);
      }
    }
  }
}
