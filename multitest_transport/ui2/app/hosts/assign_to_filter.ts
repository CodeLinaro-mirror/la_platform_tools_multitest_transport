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

import {LiveAnnouncer} from '@angular/cdk/a11y';
import {Component, EventEmitter, Input, OnChanges, OnDestroy, OnInit, Output, SimpleChanges, ChangeDetectionStrategy} from '@angular/core';
import {UntypedFormControl} from '@angular/forms';
import {ReplaySubject} from 'rxjs';
import {startWith, takeUntil} from 'rxjs/operators';

import {HostAssignInfo} from '../services/mtt_lab_models';
import {Notifier} from '../services/notifier';

/**
 * An input box with exposed dropdown menus which allows users to select lab
 * owners from the menu or input username to assign hosts to specified user.
 */
@Component({
  changeDetection: ChangeDetectionStrategy.Eager,standalone: false,
  selector: 'assign-to-filter',
  styleUrls: ['assign_to_filter.css'],
  templateUrl: './assign_to_filter.ng.html',
})
export class AssignToFilter implements OnChanges, OnInit, OnDestroy {
  @Input() selectedHostnames: string[] = [];
  @Input() dataSource: string[] = [];
  @Input() disabled: boolean = false;

  @Output() readonly submit = new EventEmitter<HostAssignInfo>();

  private readonly destroy = new ReplaySubject<void>();
  valueControl = new UntypedFormControl();
  filteredOptions: string[] = this.dataSource;

  assignTo(assignee: string = this.valueControl.value) {
    assignee = (assignee || '').trim();
    if (assignee) {
      const assignInfo:
          HostAssignInfo = {hostnames: this.selectedHostnames, assignee};
      this.submit.emit(assignInfo);
    } else {
      this.notifier.showError('Please select or enter a user name');
    }
  }

  constructor(
      protected readonly liveAnnouncer: LiveAnnouncer,
      protected readonly notifier: Notifier,
  ) {}

  changeEnabledState() {
    if (this.selectedHostnames.length > 0 && !this.disabled) {
      this.valueControl.enable();
    } else {
      this.valueControl.disable();
    }
  }

  filterOptions(value: string) {
    this.filteredOptions = value ?
        this.dataSource.filter(x => x.indexOf(value) >= 0) :
        this.dataSource;
  }

  ngOnChanges(changes: SimpleChanges) {
    if (changes['selectedHostnames']) {
      this.changeEnabledState();
    }
  }

  ngOnDestroy() {
    this.destroy.next();
  }

  ngOnInit() {
    if (this.disabled) {
      this.valueControl.disable();
    }
    this.valueControl.valueChanges
        .pipe(
            startWith(''),
            takeUntil(this.destroy),
            )
        .subscribe(
            (result) => {
              this.filterOptions(result);
              this.liveAnnouncer.announce(
                  'Loading options complete', 'assertive');
            },
            () => {
              this.notifier.showError('Failed to load options');
            },
        );
  }
}
