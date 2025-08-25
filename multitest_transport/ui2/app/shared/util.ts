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

// This util file will include helper functions used across mtt ui2
import {HttpErrorResponse} from '@angular/common/http';
import {ElementRef} from '@angular/core';
import * as moment from 'moment';
import {timer} from 'rxjs';
import {mapTo, switchMap} from 'rxjs/operators';

import {ALL_OPTIONS_VALUE} from '../services/mtt_lab_models';
import {CommandAttempt} from '../services/tfc_models';


/** Page modes for edit/view pages. */
export enum FormMode {
  NEW = 'NEW',
  EDIT = 'EDIT',
  VIEW = 'VIEW',
}

// A custom interface for moment-duration-format.
interface Duration extends moment.Duration {
  // tslint:disable-next-line:no-any
  format(template: string, precision?: string, settings?: any): string;
}

/**
 * Convert string array to string
 *
 * @param arr: a string array
 * @param delimiter: a delimiter for connecting string
 * @return a string by connecting array from delimiter
 */
export function arrayToString(arr: string[], delimiter: string) {
  arr = arr || [];
  return arr.join(delimiter);
}

/**
 * Compare length and elements of two arrays.
 *
 * @param first: the first array.
 * @param second: the second array.
 * @return a boolean that indicates whether the arrays are equal.
 */
export function areArraysEqual<T>(first: T[], second: T[]) {
  return first.length === second.length &&
      first.every((element, index) => element === second[index]);
}

/**
 * Assert whether obj is defined or not
 *
 * @param obj: any object type
 * @param fieldName: name of the object you are asserting
 * @param componentName: name of the component this object resides in
 */
export function assertRequiredInput(
    obj: unknown, fieldName: string, componentName: string) {
  if (obj === undefined) {
    throw new Error(`[${fieldName}] is a required field in ${componentName}`);
  }
}

/** Returns a deep copy of the specified value. */
export function deepCopy<T>(value: T): T {
  return value && JSON.parse(JSON.stringify(value)) as T;
}

/** Replacement for rxjs delay() which is compatible with fakeAsync. */
export function delay<T>(ms: number|Date) {
  return switchMap((value: T) => timer(ms).pipe(mapTo(value)));
}

const FNMATCH_PATTERN = /(\*|\?|\[.*\])/;
/**
 * Check whether the user provided text is a pattern that fnmatch would
 * match or not
 *
 * Supported syntax: https://docs.python.org/2/library/fnmatch.html
 */
export const isFnmatchPattern = (s: string) => FNMATCH_PATTERN.test(s);

/**
 * Convert milliseconds to a time duration in format HHH:MM:SS
 */
export function millisToDuration(millis?: number): string {
  if (millis || millis === 0) {
    return (moment.duration(millis) as Duration).format('hh:mm:ss', undefined, {
      trim: false
    });
  }
  return '';
}

/** Scroll to the first element in the ElementRef List */
export function navigateToFirstElement(inputs: ElementRef[]) {
  if (!inputs || !inputs.length) {
    return;
  }
  inputs[0].nativeElement.scrollIntoView({behavior: 'smooth', block: 'center'});
}

/** Noop function to ignore awaiting promises */
export function noAwait(result: {then: Function}) {}

/** Reloads the page after an optional delay (milliseconds) */
export async function reloadPage(delayMs?: number) {
  if (delayMs) {
    await sleep(delayMs);
  }
  window.location.reload();
}

/**
 * Mark all steps (optionally starting from a given index) as incomplete.
 * This function is used across stepper.
 */
export function resetStepCompletion(
    startingIndex: number = 0,
    stepCompletionStatusMap: {[stepIndex: number]: boolean},
    totalSteps: number) {
  for (let i = startingIndex; i < totalSteps; i++) {
    stepCompletionStatusMap[i] = false;
  }
}

/** Returns a promise that resolves after the given time in milliseconds */
export function sleep(ms: number) {
  return new Promise(resolve => {
    setTimeout(resolve, ms);
  });
}

/** Return an array with unique values. */
export function distinctArray<T>(source: T[]): T[] {
  return [...new Set(source)];
}

/** Removes the first instance of an element from an array. */
export function removeFirst<T>(array: T[], element: T): boolean {
  const index = array.indexOf(element);
  if (index > -1) {
    array.splice(index, 1);
    return true;
  }
  return false;
}


/**
 * Return the messages contained in HttpErrorResponse if there's any
 */
export function buildApiErrorMessage(errorResponse: HttpErrorResponse) {
  // Endpoint error
  const error = errorResponse.error && errorResponse.error.error;
  if (error) {
    try {
      const errorObj = JSON.parse(error.message);
      return {
        message: errorObj['message'],
        stacktrace: formatStackTrace(errorObj['stacktrace'])
      };
    } catch {
      return {message: error.message};
    }
  }
  // If endpoint didn't raise an exception, display the general error message
  return {message: errorResponse.message};
}

function formatStackTrace(stackTraces: string[][]) {
  return stackTraces.reduce((acc: string, entry: string[]) => {
    return acc +
        `File ${entry[0]}, line ${entry[1]}, in ${entry[2]}, ${entry[3]}\n`;
  }, `Traceback (most recent call last):\n`);
}

/**
 * Gets the default value for a single value filter. The value could be
 * specified from url,last selected value stored in local storage or the first
 * value of the options.
 *
 * @param options: All the candidate options users can select.
 * @param urlParam: The value specified from url.
 * @param storedParam: Last selected value stored in local storage.
 * @param hasAllOption: Whether if there is a predefined 'All' option is
 *     included in the candidate options.
 */
export function getFilterDefaultSingleValue(
    options: string[], urlParam: string, storedParam: string,
    hasAllOption = true): string {
  if (hasAllOption && urlParam === ALL_OPTIONS_VALUE) {
    return urlParam;
  }

  if (options.includes(urlParam)) {
    return urlParam;
  }

  if (hasAllOption && storedParam === ALL_OPTIONS_VALUE) {
    return storedParam;
  }

  if (options.includes(storedParam)) {
    return storedParam;
  }

  const firstOption = options.length > 0 ? options[0] : '';
  return hasAllOption ? ALL_OPTIONS_VALUE : firstOption;
}

/**
 * Returns a relative path to an omnilab test run's output files.
 * @param attempt The command attempt to get the path for.
 */
export function getOmnilabWorkingDirPath(attempt: CommandAttempt): string {
  return `log/mh_lab_gen_files/${attempt.working_job_id}/test_${
      attempt.working_test_id}`;
}
