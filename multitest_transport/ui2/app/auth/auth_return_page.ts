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
/**
 * A component for displaying an auth return page.
 *
 * User will be redirected to this page when he/she authenticate MTT via
 * localhost/127.0.0.1, and accidently closed its parent window
 */
@Component({
  changeDetection: ChangeDetectionStrategy.Eager,standalone: false,
  selector: 'auth-return-page',
  template: '<div>{{message}}</div>',
})
export class AuthReturnPage implements OnInit {
  message = 'Authorizing';
  ngOnInit() {
    setTimeout(() => {
      this.message = 'Not Authorized';
    }, 1000);
  }
}
