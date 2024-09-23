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

import {Pipe, PipeTransform, SecurityContext} from '@angular/core';
import {DomSanitizer} from '@angular/platform-browser';

/** Converts URL strings into anchor elements. Should be bound to innerHTML. */
@Pipe({standalone: false,
       name: 'linkify'})
export class LinkifyPipe implements PipeTransform {
  constructor(private readonly sanitizer: DomSanitizer) {}

  transform(value?: string): string {
    if (!value) {
      return '';
    }
    const escaped = value.replace(/</g, '&lt;').replace(/>/g, '&gt;');
    return (this.sanitizer.sanitize(SecurityContext.HTML, escaped) || '')
        .replace(/\bhttps?:\/\/\S*/ig, '<a href="$&" target="_blank">$&</a>');
  }
}
