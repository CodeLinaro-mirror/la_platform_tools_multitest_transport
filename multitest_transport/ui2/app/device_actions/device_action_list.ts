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

import {LiveAnnouncer} from '@angular/cdk/a11y';
import {Component, OnDestroy, OnInit, ChangeDetectionStrategy} from '@angular/core';
import {ReplaySubject} from 'rxjs';
import {finalize, takeUntil} from 'rxjs/operators';

import {MttClient} from '../services/mtt_client';
import {ConfigSetInfo, DeviceAction, getNamespaceFromId} from '../services/mtt_models';
import {MttObjectMapService} from '../services/mtt_object_map';
import {Notifier} from '../services/notifier';
import {buildApiErrorMessage} from '../shared/util';

/** A component for displaying a list of device actions. */
@Component({
  changeDetection: ChangeDetectionStrategy.Eager,standalone: false,
  selector: 'device-action-list',
  styleUrls: ['device_action_list.css'],
  templateUrl: './device_action_list.ng.html',
})
export class DeviceActionList implements OnInit, OnDestroy {
  isLoading = false;
  actionNamespaceMap: {[namespace: string]: DeviceAction[]} = {};
  configSetInfoMap: {[id: string]: ConfigSetInfo} = {};

  private readonly destroy = new ReplaySubject<void>();

  constructor(
      private readonly liveAnnouncer: LiveAnnouncer,
      private readonly notifier: Notifier,
      private readonly mtt: MttClient,
      private readonly mttObjectMapService: MttObjectMapService,
  ) {}

  ngOnInit() {
    this.load();
  }

  ngOnDestroy() {
    this.destroy.next();
    this.liveAnnouncer.clear();
  }

  load() {
    this.isLoading = true;
    this.liveAnnouncer.announce('Loading', 'polite');

    // Add short delay to allow device action changes to propagate.
    setTimeout(() => {
      this.mttObjectMapService.getMttObjectMap(true /* forceUpdate */)
          .pipe(
              takeUntil(this.destroy),
              finalize(() => {
                this.isLoading = false;
              }),
              )
          .subscribe(
              objectMap => {
                this.configSetInfoMap = objectMap.configSetInfoMap;
                this.actionNamespaceMap = {};

                for (const action of Object.values(objectMap.deviceActionMap)) {
                  const namespace = getNamespaceFromId(action.id || '');
                  if (!(namespace in this.actionNamespaceMap)) {
                    this.actionNamespaceMap[namespace] = [];
                  }
                  this.actionNamespaceMap[namespace].push(action);
                }
                this.liveAnnouncer.announce(
                    'Device actions loaded', 'assertive');
              },
              error => {
                this.notifier.showError(
                    'Failed to load device action list.',
                    buildApiErrorMessage(error));
              },
          );
    }, 100);
  }

  isNamespaceSectionEditable(namespace: string): boolean {
    return !namespace || !(namespace in this.configSetInfoMap);
  }

  getNamespaceTitle(namespace: string): string {
    if (!namespace) {
      return 'Default/Custom Device Actions';
    }
    if (namespace in this.configSetInfoMap) {
      return this.configSetInfoMap[namespace].name;
    }
    return `Unknown Config Set (${namespace})`;
  }

  deleteDeviceAction(deviceAction: DeviceAction) {
    this.notifier
        .confirm(
            `Do you really want to delete device action '${
                deviceAction.name}'?`,
            'Delete device action')
        .subscribe(result => {
          if (!result) {
            return;
          }
          this.mtt.deleteDeviceAction(deviceAction.id)
              .subscribe(
                  result => {
                    this.notifier.showMessage(
                        `Device action '${deviceAction.name}' deleted`);
                    this.load();
                  },
                  error => {
                    this.notifier.showError(
                        `Failed to delete device action '${
                            deviceAction.name}.'`,
                        buildApiErrorMessage(error));
                  });
        });
  }
}
