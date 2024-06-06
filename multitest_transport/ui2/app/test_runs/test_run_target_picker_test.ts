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

import {ComponentFixture, fakeAsync, TestBed, tick} from '@angular/core/testing';
import {NoopAnimationsModule} from '@angular/platform-browser/animations';
import {provideRouter} from '@angular/router';
import {of as observableOf, throwError} from 'rxjs';

import {APP_DATA} from '../services';
import {TfcClient} from '../services/tfc_client';
import {FilterHintType} from '../services/tfc_models';
import {newMockAppData} from '../testing/mtt_lab_mocks';

import {TestRunTargetPicker} from './test_run_target_picker';
import {TestRunsModule} from './test_runs_module';

describe('TestRunTargetPicker', () => {
  let testRunTargetPicker: TestRunTargetPicker;
  let testRunTargetPickerFixture: ComponentFixture<TestRunTargetPicker>;
  let tfcClient: jasmine.SpyObj<TfcClient>;
  const appData = newMockAppData();

  beforeEach(() => {
    tfcClient = jasmine.createSpyObj(
        'tfcClient', ['getDeviceInfos', 'getFilterHintList']);
    tfcClient.getDeviceInfos.and.returnValue(observableOf({device_infos: []}));
    const hostnameFilterHints = observableOf({filter_hints: [{value: 'abc'}]});
    spyOn(hostnameFilterHints, 'subscribe').and.callThrough();
    tfcClient.getFilterHintList.and.callFake(filterHintType => {
      if (filterHintType === FilterHintType.HOST) {
        return hostnameFilterHints;
      }
      if (filterHintType === FilterHintType.PRODUCT_VARIANT) {
        return throwError(new Error('TFC error'));
      }
      return observableOf({filter_hints: []});
    });

    TestBed.configureTestingModule({
      imports: [NoopAnimationsModule, TestRunsModule],
      providers: [
        provideRouter([]),
        {provide: APP_DATA, useValue: appData},
        {provide: TfcClient, useValue: tfcClient},
      ],
    });
    testRunTargetPickerFixture = TestBed.createComponent(TestRunTargetPicker);
    testRunTargetPickerFixture.detectChanges();
    testRunTargetPicker = testRunTargetPickerFixture.componentInstance;
  });

  it('initializes a component', () => {
    expect(testRunTargetPicker).toBeTruthy();
  });

  it('updates the data correctly', () => {
    testRunTargetPicker.onDeviceListSelectionChange([]);
    expect(testRunTargetPicker.shardCount).toBe(0);

    testRunTargetPicker.onDeviceListSelectionChange(['p1']);
    expect(testRunTargetPicker.shardCount).toBe(1);
    expect(testRunTargetPicker.deviceSpecs).toEqual(['device_serial:p1']);

    testRunTargetPicker.onDeviceListSelectionChange(['p1', 'p2']);
    expect(testRunTargetPicker.deviceSpecs).toEqual([
      'device_serial:p1', 'device_serial:p2'
    ]);
  });

  it('can get the device serials', () => {
    testRunTargetPicker.deviceSpecs =
        ['device_serial:host.name.domain:some-device-serial'];
    const serials = testRunTargetPicker.getDeviceSerials();
    expect(serials[0]).toEqual('host.name.domain:some-device-serial');
  });

  it('can handle invalid serials', () => {
    testRunTargetPicker.deviceSpecs =
        ['device_serial:host.name.domain:long-serial-with whitespace '];
    const serials = testRunTargetPicker.getDeviceSerials();
    expect(serials).toEqual([]);
  });

  it('can autocomplete empty device specs', done => {
    testRunTargetPicker.getDeviceSpecsAutocompleteOptions('').subscribe(
        result => {
          expect(result.length).toBeGreaterThan(0);
          done();
        });
  });

  it('can autocomplete case-insensitive device spec keys', done => {
    testRunTargetPicker.getDeviceSpecsAutocompleteOptions('Devic').subscribe(
        result => {
          result.sort(
              (first, second) => first.value.localeCompare(second.value));
          expect(result).toEqual([
            {
              value: 'device_serial:',
              displayedValue: 'device_serial',
              reopenPanel: true
            },
            {
              value: 'device_type:',
              displayedValue: 'device_type',
              reopenPanel: true
            },
          ]);
          done();
        });
  });

  it('can autocomplete device spec keys following a semicolon', done => {
    testRunTargetPicker.getDeviceSpecsAutocompleteOptions('product:a;product')
        .subscribe(result => {
          result.sort(
              (first, second) => first.value.localeCompare(second.value));
          expect(result).toEqual([
            {
              value: 'product:a;product_variant:',
              displayedValue: 'product_variant',
              reopenPanel: true
            },
            {
              value: 'product:a;product:',
              displayedValue: 'product',
              reopenPanel: true
            },
          ]);
          done();
        });
  });

  it('can handle empty device spec keys', done => {
    testRunTargetPicker.getDeviceSpecsAutocompleteOptions(':').subscribe(
        result => {
          expect(result).toEqual([]);
          done();
        });
  });

  it('can handle unknown device spec keys', done => {
    testRunTargetPicker.getDeviceSpecsAutocompleteOptions('unknown:')
        .subscribe(result => {
          expect(result).toEqual([]);
          done();
        });
  });

  it('Can autocomplete device spec values', done => {
    testRunTargetPicker.getDeviceSpecsAutocompleteOptions('device_type:')
        .subscribe(result => {
          expect(result).toEqual([
            {
              value: 'device_type:PHYSICAL',
              displayedValue: 'PHYSICAL',
              reopenPanel: false
            },
            {
              value: 'device_type:LOCAL_VIRTUAL',
              displayedValue: 'LOCAL_VIRTUAL',
              reopenPanel: false
            },
            {
              value: 'device_type:REMOTE_VIRTUAL',
              displayedValue: 'REMOTE_VIRTUAL',
              reopenPanel: false
            }
          ]);
          done();
        });
  });

  it('can throttle queries for autocomplete device spec values',
     fakeAsync(() => {
       const deviceSpecs = 'hostname:a';
       const checkResults = (result: object[]) => {
         expect(result).toEqual([
           {value: 'hostname:abc', displayedValue: 'abc', reopenPanel: false},
         ]);
       };
       const spy = tfcClient.getFilterHintList(FilterHintType.HOST).subscribe;
       // Called by device-list.
       expect(spy).toHaveBeenCalledTimes(1);
       let subscription =
           testRunTargetPicker.getDeviceSpecsAutocompleteOptions(deviceSpecs)
               .subscribe(checkResults);
       expect(spy).toHaveBeenCalledTimes(2);

       tick(1000);
       subscription.unsubscribe();
       subscription =
           testRunTargetPicker.getDeviceSpecsAutocompleteOptions(deviceSpecs)
               .subscribe(checkResults);
       expect(spy).toHaveBeenCalledTimes(2);

       tick(30000);
       subscription.unsubscribe();
       subscription =
           testRunTargetPicker.getDeviceSpecsAutocompleteOptions(deviceSpecs)
               .subscribe(checkResults);
       expect(spy).toHaveBeenCalledTimes(3);

       tick(30000);
       subscription.unsubscribe();
     }));

  it('can handle query errors for autocomplete device spec values', done => {
    testRunTargetPicker.getDeviceSpecsAutocompleteOptions('product_variant:')
        .subscribe(result => {
          expect(result).toEqual([]);
          done();
        });
  });

  it('can autocomplete case-insensitive device spec values', done => {
    testRunTargetPicker
        .getDeviceSpecsAutocompleteOptions('product:a;sim_state:ab')
        .subscribe(result => {
          expect(result).toEqual([
            {
              value: 'product:a;sim_state:ABSENT',
              displayedValue: 'ABSENT',
              reopenPanel: false
            },
          ]);
          done();
        });
  });

  it('can handle device spec values containing colons', done => {
    testRunTargetPicker
        .getDeviceSpecsAutocompleteOptions('device_serial:sim_state:a')
        .subscribe(result => {
          expect(result).toEqual([]);
          done();
        });
  });
});
