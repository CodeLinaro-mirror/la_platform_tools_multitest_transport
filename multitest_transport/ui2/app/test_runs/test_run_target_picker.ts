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

import {Component, EventEmitter, Input, OnDestroy, OnInit, Output} from '@angular/core';
import {MatAutocompleteTrigger} from '@angular/material/autocomplete';
import {MatOptionSelectionChange} from '@angular/material/core';
import {ConnectableObservable, Observable, of as observableOf, ReplaySubject, Subject} from 'rxjs';
import {catchError, map, publishBehavior, retry, switchMap, switchMapTo, takeUntil, throttleTime} from 'rxjs/operators';

import {TfcClient} from '../services/tfc_client';
import {DeviceType, FilterHintType} from '../services/tfc_models';
import {FormChangeTracker} from '../shared/can_deactivate';

declare interface AutocompleteOption {
  value: string;
  displayedValue: string;
  // Whether to reopen the panel after this option is selected.
  reopenPanel: boolean;
}

/**
 * A component for selecting run targets.
 */
@Component({
  selector: 'test-run-target-picker',
  styleUrls: ['test_run_target_picker.css'],
  templateUrl: './test_run_target_picker.ng.html',
  providers: [{provide: FormChangeTracker, useExisting: TestRunTargetPicker}]

})
export class TestRunTargetPicker extends FormChangeTracker implements
    OnInit, OnDestroy {
  @Input() deviceSpecs: string[] = [];
  @Input() shardCount = 0;
  @Input() autoUpdate = false;
  @Input() allowPartialDeviceMatch = false;

  @Output() readonly deviceSpecsChange = new EventEmitter<string[]>();
  @Output() readonly shardCountChange = new EventEmitter<number>();
  @Output()
  readonly allowPartialDeviceMatchChange = new EventEmitter<boolean>();

  manualDeviceSpecs = false;
  // The options displayed on the UI.
  deviceSpecsAutocompleteOptions: AutocompleteOption[] = [];
  // The trigger for updating deviceSpecsAutocompleteOptions.
  private readonly deviceSpecsAutocompleteSubject = new Subject<string>();
  private readonly destroy = new ReplaySubject(1);
  // The values are either constant arrays or responses from TFC. For the
  // former, the query property is undefined. For the latter, the query property
  // is set to a subject that triggers tfcClient. It is triggered when the
  // autocomplete panel needs to display the values.
  private readonly deviceSpecSuggestion:
      {[key: string]: {values: Observable<string[]>, query?: Subject<void>}} = {
        build_id: {values: observableOf([])},
        device_serial: {values: observableOf([])},
        device_type: {
          values: observableOf([DeviceType.PHYSICAL, DeviceType.LOCAL_VIRTUAL])
        },
        hostname: {values: observableOf([])},
        product: {values: observableOf([])},
        product_variant: {values: observableOf([])},
        sim_state: {values: observableOf(['ABSENT', 'READY'])},
      };
  private readonly FILTER_HINTS_MIN_INTERVAL_MSEC = 30000;

  constructor(private readonly tfcClient: TfcClient) {
    super();
    this.deviceSpecSuggestion['hostname'].query = new Subject<void>();
    this.deviceSpecSuggestion['hostname'].values =
        this.createAutocompleteOptionObservable(
            this.deviceSpecSuggestion['hostname'].query, FilterHintType.HOST);

    this.deviceSpecSuggestion['product'].query = new Subject<void>();
    this.deviceSpecSuggestion['product'].values =
        this.createAutocompleteOptionObservable(
            this.deviceSpecSuggestion['product'].query, FilterHintType.PRODUCT);

    this.deviceSpecSuggestion['product_variant'].query = new Subject<void>();
    this.deviceSpecSuggestion['product_variant'].values =
        this.createAutocompleteOptionObservable(
            this.deviceSpecSuggestion['product_variant'].query,
            FilterHintType.PRODUCT_VARIANT);

    this.deviceSpecsAutocompleteSubject
        .pipe(
            switchMap(value => this.getDeviceSpecsAutocompleteOptions(value)),
            takeUntil(this.destroy))
        .subscribe(options => {
          this.deviceSpecsAutocompleteOptions = options;
        });
  }

  ngOnInit() {
    this.deviceSpecsAutocompleteSubject.next(this.getDeviceSpecsString());
  }

  ngOnDestroy() {
    this.destroy.next();
  }

  private createAutocompleteOptionObservable(
      query: Subject<void>, queryType: FilterHintType): Observable<string[]> {
    const observable = query.pipe(
        throttleTime(this.FILTER_HINTS_MIN_INTERVAL_MSEC),
        switchMapTo(this.tfcClient.getFilterHintList(queryType).pipe(
            retry(2), catchError(() => observableOf()))),
        map(filterHintList => (filterHintList.filter_hints ||
                               []).map(filterHint => filterHint.value)),
        takeUntil(this.destroy), publishBehavior([] as string[]));
    (observable as ConnectableObservable<string[]>).connect();
    return observable;
  }

  getDeviceSerials(): string[] {
    const deviceSerials: string[] = [];
    for (const spec of this.deviceSpecs || []) {
      const match = /^device_serial:(\S+)$/.exec(spec);
      if (match) {
        deviceSerials.push(match[1]);
      }
    }
    return deviceSerials;
  }

  /**
   * This function converts a device specs string to autocomplete options. The
   * string consists of device specs separated by ';'. A device spec consists of
   * key-value pairs separated by ' '. A key and a value are separated by ':'.
   * This function first determines whether the suffix of the string is a
   * partial key or a partial value, and then filters the options by the suffix.
   * When the user selects any option, it is appended to the input field.
   */
  getDeviceSpecsAutocompleteOptions(specs: string):
      Observable<AutocompleteOption[]> {
    const keyBegin =
        Math.max(0, specs.lastIndexOf(' ') + 1, specs.lastIndexOf(';') + 1);
    const colon = specs.indexOf(':', keyBegin);
    if (colon < 0) {
      // The suffix is a key.
      const prefix = specs.slice(0, keyBegin);
      const partialKey = specs.slice(keyBegin);
      return observableOf(
          Object.keys(this.deviceSpecSuggestion)
              .filter(
                  key => key.toLowerCase().includes(partialKey.toLowerCase()))
              .map(key => ({
                     value: prefix + key + ':',
                     displayedValue: key,
                     reopenPanel: true
                   })));
    } else {
      // The suffix is a value.
      const key = specs.slice(keyBegin, colon);
      const suggestion = this.deviceSpecSuggestion[key];
      if (suggestion) {
        suggestion.query?.next();
        const prefix = specs.slice(0, colon + 1);
        const partialValue = specs.slice(colon + 1);
        return suggestion.values.pipe(
            map(values => values
                              .filter(
                                  value => value.toLowerCase().includes(
                                      partialValue.toLowerCase()))
                              .map(value => ({
                                     value: prefix + value,
                                     displayedValue: value,
                                     reopenPanel: false
                                   }))));
      }
    }
    return observableOf<AutocompleteOption[]>([]);
  }

  getDeviceSpecsString(): string {
    return (this.deviceSpecs || []).join(';');
  }

  onDeviceSpecsModelChange(deviceSpecsString: string) {
    this.deviceSpecs = (deviceSpecsString || '').split(';');
    this.deviceSpecsAutocompleteSubject.next(deviceSpecsString);
    this.deviceSpecsChange.emit(this.deviceSpecs);
  }

  onDeviceSpecsAutocomplete(
      event: MatOptionSelectionChange, option: AutocompleteOption,
      trigger: MatAutocompleteTrigger) {
    if (event.source.selected && option.reopenPanel) {
      setTimeout(() => {
        trigger.openPanel();
      });
    }
  }

  /**
   * When devices are selected in device list section, update shard count and
   * run target info.
   */
  onDeviceListSelectionChange(deviceSerials: string[]) {
    if (!this.manualDeviceSpecs) {
      this.deviceSpecs = deviceSerials.map(serial => `device_serial:${serial}`);
      this.deviceSpecsAutocompleteSubject.next(this.getDeviceSpecsString());
      this.deviceSpecsChange.emit(this.deviceSpecs);
      this.shardCount = deviceSerials.length;
      this.shardCountChange.emit(this.shardCount);
    }
  }
}
