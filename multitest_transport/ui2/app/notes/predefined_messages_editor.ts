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

import {HttpErrorResponse} from '@angular/common/http';
import {Component, Inject, OnDestroy, OnInit} from '@angular/core';
import {UntypedFormControl, UntypedFormGroup, ValidationErrors, ValidatorFn} from '@angular/forms';
import {MAT_DIALOG_DATA, MatDialogRef} from '@angular/material/dialog';
import {Notifier} from 'google3/third_party/py/multitest_transport/ui2/app/services/notifier';
import {ReplaySubject} from 'rxjs';
import {finalize, takeUntil} from 'rxjs/operators';

import {covertToPredefinedMessageType, CreatePredefinedMessageInfo, MessageCategory, MessageType} from '../services/mtt_lab_models';
import {TfcClient} from '../services/tfc_client';
import {PredefinedMessage, PredefinedMessageType} from '../services/tfc_models';

/** Possible action for note editor. */
export enum PredefinedMessagesEditorAction {
  CREATE = 'CREATE',
  UPDATE = 'UPDATE',
}

/** Editor input validation, to ensure all input field has value. */
export const allRequired: ValidatorFn = (forms): ValidationErrors|null => {
  const labFormControl = forms.get('labFormControl');
  const messageCategoryFormControl = forms.get('messageCategoryFormControl');
  const messageTypeFormControl = forms.get('messageTypeFormControl');
  const contentFormControl = forms.get('contentFormControl');

  if (!labFormControl!.value || !messageCategoryFormControl!.value ||
      !messageTypeFormControl!.value || !contentFormControl!.value) {
    return {'allRequired': true};
  }
  return null;
};

/** Params for the predefined message editor dialog. */
export interface PredefinedMessagesEditorDialogParams {
  predefinedMessage: PredefinedMessage|undefined;
  defaultMessageCategory: string;
  defaultMessageType: string;
  defaultLab: string;
}

/** Creates or edit predefined message. */
@Component({
  selector: 'predefined-messages-editor',
  styleUrls: ['predefined_messages_editor.css'],
  templateUrl: './predefined_messages_editor.ng.html',
})
export class PredefinedMessagesEditor implements OnInit, OnDestroy {
  forms: UntypedFormGroup;
  action = PredefinedMessagesEditorAction.CREATE;
  messageCategories: string[] = [];
  messageTypes: string[] = [];
  isEditMode = false;
  isLoading = false;

  selectedLab = '';
  selectedMessageCategory = '';
  selectedMessageType = '';

  private readonly destroy = new ReplaySubject<void>();

  constructor(
      @Inject(MAT_DIALOG_DATA) readonly params:
          PredefinedMessagesEditorDialogParams,
      private readonly dialogRef: MatDialogRef<PredefinedMessage>,
      private readonly notifier: Notifier,
      private readonly tfcClient: TfcClient,
  ) {
    this.action = this.params.predefinedMessage ?
        PredefinedMessagesEditorAction.UPDATE :
        PredefinedMessagesEditorAction.CREATE;
    this.isEditMode = this.action === PredefinedMessagesEditorAction.UPDATE;
    this.selectedLab = this.params.defaultLab;
    this.forms = this.createFormGroup(this.params);
  }

  ngOnInit() {
    this.messageCategories = Object.values(MessageCategory);
    this.messageTypes = Object.values(MessageType);
    this.setDefaultValue(this.params);
  }

  ngOnDestroy() {
    this.destroy.next();
  }

  closeEditorDialog() {
    this.dialogRef.close();
  }

  createFormGroup(params: PredefinedMessagesEditorDialogParams):
      UntypedFormGroup {
    return new UntypedFormGroup(
        {
          'labFormControl': new UntypedFormControl(this.selectedLab),
          'messageCategoryFormControl': new UntypedFormControl(
              {value: this.selectedMessageCategory, disabled: this.isEditMode}),
          'messageTypeFormControl': new UntypedFormControl(
              {value: this.selectedMessageType, disabled: this.isEditMode}),
          'contentFormControl': new UntypedFormControl(''),
        },
        {validators: allRequired});
  }

  /** Sets input field vaule by device note or host note. */
  setDefaultValue(params: PredefinedMessagesEditorDialogParams) {
    this.forms.patchValue({
      'labFormControl': params.defaultLab,
      'messageCategoryFormControl': params.defaultMessageCategory,
      'messageTypeFormControl': params.defaultMessageType,
    });

    if (params.predefinedMessage) {
      this.forms.patchValue({
        'contentFormControl': params.predefinedMessage.content,
      });
    }
  }

  save() {
    const predefinedMessageType = this.getCurrentPredefinedMessageType();

    if (this.forms.valid && predefinedMessageType) {
      const predefinedMessageInfo: CreatePredefinedMessageInfo = {
        labName: this.forms.get('labFormControl')!.value,
        predefinedMessageType,
        content: this.forms.get('contentFormControl')!.value.trim(),
      };

      if (!this.params.predefinedMessage) {
        this.createPredefinedMessage(predefinedMessageInfo);
      } else {
        const id = this.params.predefinedMessage.id;
        const content = this.forms.get('contentFormControl')!.value.trim();
        this.updatePredefinedMessage(id, content);
      }
    }
  }

  createPredefinedMessage(predefinedMessageInfo: CreatePredefinedMessageInfo) {
    this.isLoading = true;
    this.tfcClient.createPredefinedMessage(predefinedMessageInfo)
        .pipe(
            takeUntil(this.destroy),
            finalize(() => {
              this.isLoading = false;
            }),
            )
        .subscribe(
            (result) => {
              this.notifier.showMessage('Predefined message created');
              this.dialogRef.close(result);
            },
            (err: HttpErrorResponse) => {
              if (err.error.error.code === 409) {
                this.notifier.showError(
                    'This predefined message has already existed');
              } else {
                this.notifier.showError('Failed to create predefined message');
              }
            });
  }

  updatePredefinedMessage(id: number, content: string) {
    this.isLoading = true;
    this.tfcClient.updatePredefinedMessage(id, content)
        .pipe(
            takeUntil(this.destroy),
            finalize(() => {
              this.isLoading = false;
            }),
            )
        .subscribe(
            (result) => {
              this.notifier.showMessage('Predefined message updated');
              this.dialogRef.close(result);
            },
            (err: HttpErrorResponse) => {
              if (err.error.error.code === 409) {
                this.notifier.showError(
                    'This predefined message has already existed');
              } else {
                this.notifier.showError('Failed to update predefined message');
              }
            });
  }

  getCurrentPredefinedMessageType(): PredefinedMessageType|undefined {
    return covertToPredefinedMessageType(
        this.forms.get('messageCategoryFormControl')!.value,
        this.forms.get('messageTypeFormControl')!.value);
  }
}
