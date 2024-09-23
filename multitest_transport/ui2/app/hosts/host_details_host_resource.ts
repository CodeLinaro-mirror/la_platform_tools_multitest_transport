/**
 * Copyright 2021 Google LLC
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
import {Component, Input, OnChanges, OnDestroy, OnInit, SimpleChanges} from '@angular/core';
import {ReplaySubject} from 'rxjs';
import {takeUntil} from 'rxjs/operators';

import {Notifier} from '../services/notifier';
import {TfcClient} from '../services/tfc_client';
import {assertRequiredInput} from '../shared/util';
import {LabHostResource} from '../services/mtt_lab_models';


declare interface NameValueTimeTuple {
  name: string;
  value: string;
  time: string|null;
}


/** Displaying extra info list of a host. */
@Component({
  standalone: false,
  selector: 'host-details-host-resource',
  styleUrls: ['host_details_host_resource.css'],
  templateUrl: 'host_details_host_resource.ng.html',
})
export class HostDetailsHostResource implements OnChanges, OnInit, OnDestroy {
  @Input() id!: string;
  hostResourceNameValueTimes: NameValueTimeTuple[] = [];
  hostResource: LabHostResource|null = null;

  private readonly destroy = new ReplaySubject<void>();

  displayedColumns: string[] = [
    'name', 'value', 'time'
  ];

  constructor(
      private readonly liveAnnouncer: LiveAnnouncer,
      private readonly notifier: Notifier,
      private readonly tfcClient: TfcClient,
  ) {}

  ngOnChanges(changes: SimpleChanges) {
    if (changes['id'] && !changes['id'].firstChange) {
      this.loadHostResource(this.id);
    }
  }

  ngOnInit() {
    assertRequiredInput(this.id, 'id', 'host-details-host-resource');
    this.loadHostResource(this.id);
  }

  ngOnDestroy() {
    this.destroy.next();
  }

  /**
   * Loads a page of hostInfo history to the stored page tokens.
   * @param hostname Unique host name
   */
  loadHostResource(hostname: string) {
    this.tfcClient.getHostResource(hostname)
        .pipe(
            takeUntil(this.destroy),
            )
        .subscribe(
            (result) => {
              this.hostResource = result;
              this.hostResourceNameValueTimes =
                  this.hostResourceToNameValueTimes(result);
              console.log(this.hostResource);
              this.liveAnnouncer.announce('Host resource loaded.', 'assertive');
            },
            (error) => {
              this.notifier.showError(
                  `Failed to load host resource for host ${hostname}`);
            },
        );
  }

  /** Convert a LabHostResource to a list of name, value and time tuples. */
  hostResourceToNameValueTimes(hostResource: LabHostResource|null):
      NameValueTimeTuple[] {
    let res: NameValueTimeTuple[] = [];
    if (!hostResource) {
      return res;
    }
    res = res.concat(hostResource.resource.attribute.map(attribute =>
      ({
        name: attribute.name,
        value: attribute.value,
        time: hostResource.event_timestamp
      })));
    res = res.concat(hostResource.resource.resource.map(resource => {
      let name: string = resource.resource_name;
      if (resource.resource_instance) {
        name += ' ' + resource.resource_instance;
      }
      const value: string = resource.metric.map(
          metric => metric.tag + '=' + metric.value).join(', ');
      return {name, value, time: resource.timestamp};
    }));
    return res;
  }
}
