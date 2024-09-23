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

import {Component, Input, OnChanges, OnInit, SimpleChanges} from '@angular/core';
import {assertRequiredInput} from '../shared/util';
import {LabHostExtraInfo} from '../services/mtt_lab_models';


/** Displaying extra info list of a host. */
@Component({
  standalone: false,
  selector: 'host-details-extra-infos',
  styleUrls: ['host_details_extra_infos.css'],
  templateUrl: 'host_details_extra_infos.ng.html',
})
export class HostDetailsExtraInfos implements OnChanges, OnInit {
  @Input() extraInfo!: LabHostExtraInfo;
  extraInfoList: Array<{key: string, value: string|number}> = [];

  displayedColumns: string[] = [
    'key', 'value'
  ];

  ngOnChanges(changes: SimpleChanges) {
    if (changes['extraInfo']) {
      this.extraInfo = changes['extraInfo'].currentValue;
      this.extraInfoList = this.extraInfoToExtraInfoList(this.extraInfo);
    }
  }

  ngOnInit() {
    assertRequiredInput(
        this.extraInfo, 'extraInfo', 'host-details-extra-infos');
    this.extraInfoList = this.extraInfoToExtraInfoList(this.extraInfo);
  }

  /**
   * LabHostExtraInfo object to a list of key value pairs.
   * @param extraInfo a LabHostExtraInfo
   */
  extraInfoToExtraInfoList(extraInfo: LabHostExtraInfo) {
    return Object.entries(extraInfo).map(o => ({key: o[0], value: o[1]}));
  }
}
