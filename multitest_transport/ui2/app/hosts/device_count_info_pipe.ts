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

import {PercentPipe} from '@angular/common';
import {Inject, LOCALE_ID, Pipe, PipeTransform} from '@angular/core';

import {LabHostExtraInfo} from '../services/mtt_lab_models';

/**
 * Returns a string containing the value and percentage of the device status.
 */
@Pipe({standalone: false,
       name: 'deviceCountInfo'})
export class DeviceCountInfoPipe implements PipeTransform {
  constructor(@Inject(LOCALE_ID) private readonly locale: string) {}
  transform(hostExtraInfo: LabHostExtraInfo, target: string): string {
    switch (target) {
      case 'total':
        return hostExtraInfo.total_devices;
      case 'online':
        const total = Number(hostExtraInfo.total_devices);
        const offline = Number(hostExtraInfo.offline_devices);
        return hostExtraInfo.total_devices && hostExtraInfo.offline_devices ?
            this.deviceCountInfo(total - offline, total, true) :
            '';
      case 'available':
        return hostExtraInfo.total_devices && hostExtraInfo.available_devices ?
            this.deviceCountInfo(
                Number(hostExtraInfo.available_devices),
                Number(hostExtraInfo.total_devices)) :
            '';
      case 'allocated':
        return hostExtraInfo.total_devices && hostExtraInfo.allocated_devices ?
            this.deviceCountInfo(
                Number(hostExtraInfo.allocated_devices),
                Number(hostExtraInfo.total_devices)) :
            '';
      default:
        // nothing to do.
    }
    return ``;
  }

  deviceCountInfo(count: number, total: number, showExcludedCount = false):
      string {
    if (Number.isNaN(count) || Number.isNaN(total)) {
      return '';
    }
    const percentPipe = new PercentPipe(this.locale);
    const percentage =
        total === 0 ? '0%' : percentPipe.transform(count / total, '1.1');
    const excludedCount = total - count;
    const excludedCountDisplay =
        showExcludedCount ? `(-${excludedCount}) ` : '';
    return `${count} ${excludedCountDisplay}(${percentage})`;
  }
}
