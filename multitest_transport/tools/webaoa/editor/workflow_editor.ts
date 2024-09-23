/**
 * @license
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

import {Clipboard} from '@angular/cdk/clipboard';
import {CdkDragDrop, moveItemInArray} from '@angular/cdk/drag-drop';
import {Component, ElementRef, HostListener, Input, OnChanges, OnDestroy, SimpleChanges, ViewChild} from '@angular/core';
import {MatDialog} from '@angular/material/dialog';
import {MatSnackBar} from '@angular/material/snack-bar';
import {firstValueFrom, Observable, Subject} from 'rxjs';

import {AoaDevice, Key} from '../device/device';
import {FindDeviceDialog} from '../device/find_device_dialog';

import {AoaAction, BackAction, HomeAction, KeyAction, SleepAction, WakeAction} from './action';
import {AoaActionEditor, AoaActionEditorResult} from './action_editor';
import {ExecutionWakeLock} from './wake_lock';

// Google Analytics global site tag (defined in index.html).
declare var gtag: (type: 'event', action: string, params: object) => void;
// True if Google Analytics is enabled (defined in index.html).
declare var analyticsEnabled: boolean;
// Extra parameters to send with analytics requests (defined in index.html).
declare var analyticsParams: object;

/** Track an event by sending it to Google Analytics if enabled. */
function trackEvent(action: string, label?: string) {
  if (typeof analyticsEnabled === 'undefined' || !analyticsEnabled) return;
  gtag('event', action, {
    ...analyticsParams,
    'event_category': 'webaoa',
    'event_label': label,
  });
}

/** Milliseconds to wait between actions. */
export const ACTION_DELAY_MILLIS = 3000;
/** Maximum time between keys in a combination. */
export const MAX_KEY_COMBINATION_MILLIS = 2000;

/**
 * Manages a list of AOA actions. Can be used to add new actions using a series
 * of controls, to rearrange or delete existing actions, and to execute actions
 * on the selected device.
 */
@Component({
  standalone: false,
  selector: 'workflow-editor',
  templateUrl: './workflow_editor.ng.html',
  styleUrls: ['./workflow_editor.css'],
})
export class WorkflowEditor implements OnChanges, OnDestroy {
  readonly ENTER = Key.ENTER;
  readonly TAB = Key.TAB;
  readonly UP = Key.UP;
  readonly RIGHT = Key.RIGHT;
  readonly DOWN = Key.DOWN;
  readonly LEFT = Key.LEFT;

  // hidden file upload and download elements
  @ViewChild('uploader') uploader?: ElementRef;
  @ViewChild('downloader') downloader?: ElementRef;

  /** Device to execute actions on. */
  @Input() device?: AoaDevice;
  /** Tracks whether the device is currently busy. */
  isDeviceBusy = false;
  /** List of actions in the workflow. */
  actions: AoaAction[] = [];
  /** Emits whenever the cancel button is pressed. */
  cancel = new Subject<void>();
  /** Action currently being executed. */
  executing?: AoaAction;
  /** Last key pressed. */
  private lastKey?: KeyAction;
  /** Timestamp of the last key press. */
  private lastKeyTime?: number;

  constructor(
      private readonly clipboard: Clipboard, private readonly dialog: MatDialog,
      private readonly snackBar: MatSnackBar,
      private readonly wakeLock: ExecutionWakeLock) {}

  async ngOnChanges(changes: SimpleChanges) {
    const device = changes['device'];
    if (device && device.previousValue !== device.currentValue) {
      await this.closeDevice(device.previousValue);
      this.device = await this.prepareDevice(device.currentValue);
    }
  }

  @HostListener('window:unload')
  async ngOnDestroy() {
    // Must close the connection when closing the application to ensure that any
    // custom HIDs are unregistered.
    await this.closeDevice(this.device);
  }

  /** Prepares a device for AOA execution. */
  private async prepareDevice(device?: AoaDevice, reset = false):
      Promise<AoaDevice|undefined> {
    if (!device) {
      return;
    }
    try {
      this.isDeviceBusy = true;
      try {
        await (reset ? device.reset() : device.open());
      } finally {
        this.isDeviceBusy = false;
      }
      return device;
    } catch (error) {
      // If an error occurs while opening or resetting the connection, prompt
      // the user to either reselect the device and re-open or cancel.
      return this.prepareDevice(await this.findDevice(device));
    }
  }

  /** Prompt user to locate a device if its connection was unexpectedly lost. */
  private findDevice(device: AoaDevice): Promise<AoaDevice|undefined> {
    const dialogRef = this.dialog.open(
        FindDeviceDialog,
        {width: '600px', disableClose: true, data: device.serialNumber});
    return firstValueFrom(dialogRef.afterClosed());
  }

  /** Close a device's connection. */
  private async closeDevice(device?: AoaDevice) {
    if (!device) {
      return;
    }
    await device.close();
  }

  /** Handle uploading a workflow file. */
  async uploadWorkflowFile() {
    trackEvent('upload_workflow');
    const file = this.uploader!.nativeElement.files[0];
    this.actions = await this.readWorkflowFromFile(file);
  }

  /** Handle dragging-and-dropping a workflow file. */
  async dropWorkflowFile(event: DragEvent) {
    trackEvent('upload_workflow');
    event.preventDefault();
    const file = event.dataTransfer!.files[0];
    this.actions = await this.readWorkflowFromFile(file);
  }

  /** Handle copy-pasting a workflow. */
  pasteWorkflowData(event: ClipboardEvent) {
    trackEvent('paste_workflow');
    const data = event.clipboardData!.getData('text/plain');
    this.actions = this.parseWorkflowFromString(data);
  }

  /** Read and parse a workflow from a file. */
  private readWorkflowFromFile(file: File): Promise<AoaAction[]> {
    return new Promise<AoaAction[]>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        try {
          resolve(this.parseWorkflowFromString(reader.result as string));
        } catch (error) {
          reject(error);
        }
      };
      reader.onerror = () => {
        reject(reader.error);
      };
      reader.readAsText(file);
    });
  }

  /** Parse a workflow string into a list of actions. */
  private parseWorkflowFromString(data: string): AoaAction[] {
    const actions: AoaAction[] = [];
    for (const line of data.split('\n')) {
      if (!line.trim()) {
        continue;  // ignore blank line
      }
      actions.push(AoaAction.parse(line));
    }
    return actions;
  }

  /** Serializes each action and copies it to the clipboard. */
  copyWorkflowToClipboard() {
    trackEvent('copy_workflow');
    const content = this.actions.map(action => action.toString()).join('\n');
    this.clipboard.copy(content);
    this.snackBar.open('Workflow copied!', 'Dismiss', {duration: 3000});
  }

  /** Serializes each action and writes it to a file. */
  saveWorkflowToFile() {
    trackEvent('save_workflow');
    const content = this.actions.map(action => action.toString()).join('\n');
    const url = `data:text/plain;base64,${btoa(content)}`;
    this.downloader!.nativeElement.setAttribute('download', 'workflow');
    this.downloader!.nativeElement.setAttribute('href', url);
    this.downloader!.nativeElement.click();
  }

  /** Deletes all actions in the workflow. */
  clearWorkflow() {
    this.actions = [];
  }

  /**
   * Appends a new action to the workflow.
   * @param action action to append
   * @param execute true to execute the action after appending
   */
  appendAction(action: AoaAction, execute = true) {
    this.actions.push(action);
    if (execute) {
      this.executeActions([action]);
    }
  }

  /**
   * Rearranges a pair of actions.
   * @param event drag and drop event
   */
  moveAction(event: CdkDragDrop<AoaAction[]>) {
    moveItemInArray(this.actions, event.previousIndex, event.currentIndex);
  }

  /**
   * Edits an action.
   * @param index index of the action to edit
   */
  editAction(index: number) {
    const action = this.actions[index];
    this.openActionEditor(action).subscribe(result => {
      if (result) {
        this.actions[index] = result.action;
        if (result.execute) {
          this.executeActions([result.action]);
        }
      }
    });
  }

  /** Opens the action editor and returns the updated action. */
  private openActionEditor(action: string|AoaAction):
      Observable<AoaActionEditorResult|undefined> {
    return this.dialog
        .open<AoaActionEditor, string, AoaActionEditorResult>(AoaActionEditor, {
          width: '700px',
          disableClose: true,
          data: action.toString(),
        })
        .afterClosed();
  }

  /**
   * Deletes an action.
   * @param index index of the action to delete
   */
  deleteAction(index: number) {
    this.actions.splice(index, 1);
  }

  /**
   * Executes a series of actions with a delay between each.
   * @param actions list of actions to execute
   * @param delay milliseconds to wait between actions
   */
  async executeActions(actions: AoaAction[], delay = ACTION_DELAY_MILLIS):
      Promise<void> {
    const cancellation = this.getCancellationPromise();
    this.isDeviceBusy = true;
    this.wakeLock.acquire();
    try {
      for (let i = 0; i < actions.length; i++) {
        const action = actions[i];
        const hasMore = i < actions.length - 1;
        await this.executeAction(action, hasMore ? delay : 0, cancellation);
      }
    } finally {
      this.wakeLock.release();
      this.executing = undefined;
      this.isDeviceBusy = false;
    }
  }

  /**
   * Creates a promise which will be rejected with a cancellation error the next
   * time the cancel button is pressed.
   * @return cancellation promise
   */
  private getCancellationPromise(): Promise<void> {
    return firstValueFrom(this.cancel).then(() => {
      throw new Error('Execution cancelled');
    });
  }

  /**
   * Executes a single action and marks it as active. Checks if the device is
   * ready and resets it if necessary. Stops the execution if it canceled.
   */
  private async executeAction(
      action: AoaAction, delay: number,
      cancellation: Promise<void>): Promise<void> {
    if (this.device && !this.device.isConnected()) {
      this.device = await this.prepareDevice(this.device, true);
    }
    if (!this.device) {
      return;
    }
    this.executing = action;
    trackEvent('execute_action', action.command);
    await Promise.race([action.execute(this.device), cancellation]);
    await Promise.race([this.device.sleep(delay), cancellation]);
  }

  /**
   * Appends a new sleep action to the workflow.
   * @param millis sleep milliseconds
   */
  appendSleepAction(millis: number) {
    this.appendAction(new SleepAction(millis), false);
  }

  /** Appends a new back action to the workflow. */
  appendBackAction() {
    this.appendAction(new BackAction());
  }

  /** Appends a new home action to the workflow. */
  appendHomeAction() {
    this.appendAction(new HomeAction());
  }

  /** Appends a new wake action to the workflow. */
  appendWakeAction() {
    this.appendAction(new WakeAction());
  }

  /** Appends a new back action to the workflow. */
  appendWriteAction() {
    this.openActionEditor('write').subscribe(result => {
      if (result) {
        this.appendAction(result.action, result.execute);
      }
    });
  }

  /**
   * Appends a new key action to the workflow or, if the another key was pressed
   * recently, append an additional key to that key action.
   */
  appendKeyAction(key: Key) {
    let action = new KeyAction([key]);
    const index = this.actions.length - 1;

    if (this.lastKey && this.lastKeyTime &&
        this.actions[index] === this.lastKey &&
        Date.now() - this.lastKeyTime < MAX_KEY_COMBINATION_MILLIS) {
      // last key press occurred recently and no other actions were added,
      // execute the current action and replace the previous action
      this.executeActions([action]);
      action = new KeyAction([...this.lastKey.keys, key]);
      this.actions[index] = action;
    } else {
      // append and execute current action
      this.appendAction(action);
    }

    this.lastKey = action;
    this.lastKeyTime = Date.now();
  }
}
