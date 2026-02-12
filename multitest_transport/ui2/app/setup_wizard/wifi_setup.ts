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

import {Component, OnInit, ChangeDetectionStrategy} from '@angular/core';
import {Observable} from 'rxjs';
import {first} from 'rxjs/operators';

import {MttClient} from '../services/mtt_client';
import {NameValuePair, NodeConfig} from '../services/mtt_models';
import {Notifier} from '../services/notifier';
import {buildApiErrorMessage} from '../shared/util';

/**
 * This component allows users to add a WiFi name and password for the CTS
 * setup action.
 */
@Component({
  changeDetection: ChangeDetectionStrategy.Eager,standalone: false,
  selector: 'wifi-setup',
  templateUrl: './wifi_setup.ng.html',
})
export class WifiSetup implements OnInit {
  envVarMap: {[name: string]: string} = {
    'WIFI_SSID': '',
    'WIFI_PSK': '',
  };
  nodeConfig!: NodeConfig;

  constructor(
      private readonly mtt: MttClient,
      private readonly notifier: Notifier,
  ) {}

  ngOnInit() {
    this.load();
  }

  load() {
    // Get current node config
    this.mtt.getNodeConfig().pipe(first()).subscribe(
        result => {
          this.nodeConfig = result;
          this.envVarMap = this.arrayToDict(result.env_vars || []);
          this.envVarMap['WIFI_SSID'] = this.envVarMap['WIFI_SSID'] || '';
          this.envVarMap['WIFI_PSK'] = this.envVarMap['WIFI_PSK'] || '';
        },
        error => {
          this.notifier.showError(
              'Failed to load current settings.', buildApiErrorMessage(error));
        });
  }

  arrayToDict(array: NameValuePair[]): {[name: string]: string} {
    const dict: {[name: string]: string} = {};
    for (const envVar of array) {
      if (typeof envVar.name !== 'undefined') {
        dict[envVar.name] = envVar.value || '';
      }
    }
    return dict;
  }

  dictToArray(dict: {[name: string]: string}): NameValuePair[] {
    const array: NameValuePair[] = [];
    for (const name of Object.keys(dict)) {
      array.push({name, value: dict[name]});
    }
    return array;
  }

  submit(): Observable<NodeConfig> {
    this.nodeConfig.env_vars = this.dictToArray(this.envVarMap);
    return this.mtt.updateNodeConfig(this.nodeConfig);
  }
}
