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

import {Component, Input, OnInit} from '@angular/core';
import {assertRequiredInput} from 'google3/third_party/py/multitest_transport/ui2/app/shared/util';

import {HostState} from '../services/tfc_models';

/** Component for display host status in chip in recovery host list. */
@Component({
  standalone: false,
  selector: 'recovery-host-status',
  styleUrls: ['recovery_host_status.css'],
  templateUrl: './recovery_host_status.ng.html',
})
export class RecoveryHostStatus implements OnInit {
  @Input() state!: HostState;

  ngOnInit() {
    assertRequiredInput(this.state, 'state', 'HostState');
  }
}
