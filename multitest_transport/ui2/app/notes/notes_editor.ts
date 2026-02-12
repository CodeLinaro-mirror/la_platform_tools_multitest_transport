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
import {Component, EventEmitter, Input, OnDestroy, OnInit, Output, ChangeDetectionStrategy} from '@angular/core';
import {AbstractControl, UntypedFormControl, UntypedFormGroup, ValidationErrors, ValidatorFn} from '@angular/forms';
import {Notifier} from 'google3/third_party/py/multitest_transport/ui2/app/services/notifier';
import {OverflowListType} from 'google3/third_party/py/multitest_transport/ui2/app/shared/overflow_list';
import {assertRequiredInput} from 'google3/third_party/py/multitest_transport/ui2/app/shared/util';
import * as moment from 'moment';
import {forkJoin, Observable, of as observableOf, ReplaySubject} from 'rxjs';
import {catchError, filter, finalize, map, startWith, takeUntil} from 'rxjs/operators';

import {FeedbackService} from '../services/feedback_service';
import {BatchCreateOrUpdateNotesInfo, NoteType, SurveyTrigger} from '../services/mtt_lab_models';
import {TfcClient} from '../services/tfc_client';
import {Note, PredefinedMessage, PredefinedMessagesResponse, PredefinedMessageType} from '../services/tfc_models';
import {buildApiErrorMessage} from '../shared/util';

import {NoteDialogParams} from './notes_dialog';

/** Possible action for note editor. */
export enum NoteEditorAction {
  CREATE = 'CREATE',
  UPDATE = 'UPDATE',
}

/** Editor input validation, to ensure at least one input field has value. */
export const atLeastOne: ValidatorFn = (forms): ValidationErrors|null => {
  const offlineReasonsControl = forms.get('offlineReasonFormControl');
  const recoveryActionsControl = forms.get('recoveryActionFormControl');
  const messageControl = forms.get('messageFormControl');

  if ((offlineReasonsControl && !offlineReasonsControl.value) &&
      (recoveryActionsControl && !recoveryActionsControl.value) &&
      (messageControl && !messageControl.value)) {
    return {atLeastOne: true};
  }
  return null;
};

/**
 * Event date time input validation, to ensure input value can be convert to
 * date.
 */
export const dateTimeValidator: ValidatorFn =
    (control: AbstractControl): ValidationErrors|null => {
      const date = new Date(control.value);
      if (isNaN(date.getTime())) {  // Value is not a valid date.
        return {formatError: {value: control.value}};
      } else {
        return null;
      }
    };

/** Adds or Edit notes for hosts or devices. */
@Component({
  changeDetection: ChangeDetectionStrategy.Eager,standalone: false,
  selector: 'notes-editor',
  styleUrls: ['notes_editor.css'],
  templateUrl: './notes_editor.ng.html',
})
export class NotesEditor implements OnDestroy, OnInit {
  @Input() params!: NoteDialogParams;
  @Output() readonly close = new EventEmitter();
  @Output() readonly saved = new EventEmitter<boolean>();
  @Output() readonly switchToListMode = new EventEmitter<boolean>();

  readonly OverflowListType = OverflowListType;
  readonly NoteType = NoteType;

  private readonly destroy = new ReplaySubject<void>();

  forms: UntypedFormGroup;
  action = NoteEditorAction.CREATE;
  isLoading = false;
  isEditEventDate = false;

  selecetedOfflineReason = '';
  selecetedRecoveryAction = '';

  offlineReasons: PredefinedMessage[] = [];
  recoveryActions: PredefinedMessage[] = [];

  eventDateTime?: Date = undefined;
  defalutDateTimeFormat = 'YYYY-MM-DDTHH:mm:ss';
  eventDateTimeFormControl = new UntypedFormControl('', [dateTimeValidator]);

  filteredOfflineReasons: Observable<PredefinedMessage[]> =
      observableOf(this.offlineReasons);
  filteredRecoveryActions: Observable<PredefinedMessage[]> =
      observableOf(this.recoveryActions);

  constructor(
      private readonly feedbackService: FeedbackService,
      private readonly liveAnnouncer: LiveAnnouncer,
      private readonly notifier: Notifier,
      private readonly tfcClient: TfcClient,
  ) {
    this.forms = this.createFormGroup();
  }

  ngOnDestroy() {
    this.destroy.next();
  }

  ngOnInit() {
    assertRequiredInput(this.params, 'params', 'notes-editor');
    this.action =
        this.params.noteId ? NoteEditorAction.UPDATE : NoteEditorAction.CREATE;
    this.load();
  }

  createFormGroup(): UntypedFormGroup {
    return new UntypedFormGroup(
        {
          'offlineReasonFormControl':
              new UntypedFormControl(this.selecetedOfflineReason),
          'recoveryActionFormControl':
              new UntypedFormControl(this.selecetedRecoveryAction),
          'messageFormControl': new UntypedFormControl('')
        },
        {validators: atLeastOne});
  }

  load() {
    this.liveAnnouncer.announce('Loading', 'polite');
    forkJoin([this.getOfflineReason(), this.getRecoveryAction()])
        .pipe(takeUntil(this.destroy))
        .subscribe(([offlineReasonResult, recoveryActionResult]) => {
          if (offlineReasonResult.predefined_messages) {
            this.setOfflineReasons(offlineReasonResult.predefined_messages);
          }
          if (recoveryActionResult.predefined_messages) {
            this.setRecoveryActions(recoveryActionResult.predefined_messages);
          }
          if (this.params.noteId) {  // Loads note data if note id is in
                                     // NoteDialogParams.
            this.loadExitedNoteData(this.params.ids[0], this.params.noteId);
          }
        });
  }

  /** Loads device or host note data with note id. */
  loadExitedNoteData(targetId: string, noteId: number) {
    this.isLoading = true;
    if (this.params.noteType === NoteType.DEVICE) {
      this.tfcClient.batchGetDeviceNotes(targetId, [noteId])
          .pipe(
              takeUntil(this.destroy),
              finalize(() => {
                this.isLoading = false;
              }),
              )
          .subscribe(
              (result) => {
                if (result.notes) {
                  this.setDefaultValue(result.notes[0]);
                }
              },
              (error) => {
                this.notifier.showError(
                    `Failed to get note with id ${noteId}.`,
                    buildApiErrorMessage(error));
              });
    } else {
      this.tfcClient.batchGetHostNotes(targetId, [noteId])
          .pipe(
              takeUntil(this.destroy),
              finalize(() => {
                this.isLoading = false;
              }),
              )
          .subscribe(
              (result) => {
                if (result.notes) {
                  this.setDefaultValue(result.notes[0]);
                }
              },
              (error) => {
                this.notifier.showError(
                    `Failed to get note with id ${noteId}.`,
                    buildApiErrorMessage(error));
              });
    }
  }

  addEventTime() {
    this.eventDateTime = new Date();
    this.eventDateTimeFormControl.setValue(
        moment(this.eventDateTime).format(this.defalutDateTimeFormat));
    this.eventDateTimeFormControl.markAsDirty();
  }

  updateEventTime() {
    if (this.eventDateTimeFormControl.valid) {
      const newDateTime = new Date(this.eventDateTimeFormControl.value);
      this.eventDateTime = newDateTime;
      this.isEditEventDate = false;
    }
  }

  editEventTime() {
    this.isEditEventDate = true;
  }

  removeEventTime() {
    this.isEditEventDate = false;
    this.eventDateTime = undefined;
    this.eventDateTimeFormControl.setValue('');
    this.eventDateTimeFormControl.markAsDirty();
  }

  /** Sets input field vaule by device note or host note. */
  setDefaultValue(noteData: Note) {
    if (noteData.offline_reason) {
      this.forms.patchValue({
        'offlineReasonFormControl': noteData.offline_reason,
      });
    }
    if (noteData.recovery_action) {
      this.forms.patchValue({
        'recoveryActionFormControl': noteData.recovery_action,
      });
    }
    if (noteData.message) {
      this.forms.patchValue({
        'messageFormControl': noteData.message,
      });
    }
    if (noteData.event_time) {
      this.eventDateTime =
          new Date(noteData.event_time + 'Z');  // event_time is GMT + Zero.
      this.eventDateTimeFormControl.patchValue(
          moment(this.eventDateTime).format(this.defalutDateTimeFormat));
    }
  }

  /** Get offline reason list by note type and lab name. */
  getOfflineReason(): Observable<PredefinedMessagesResponse> {
    const offlineReasonType = this.params.noteType === NoteType.DEVICE ?
        PredefinedMessageType.DEVICE_OFFLINE_REASON :
        PredefinedMessageType.HOST_OFFLINE_REASON;
    const errorMessage =
        `Failed to load offline reason for lab ${this.params.labName}`;
    return this.getCommonPredefinedMessagesObservable(
        this.params.labName, offlineReasonType, errorMessage);
  }

  /** Get recovery action list by note type and lab name. */
  getRecoveryAction(): Observable<PredefinedMessagesResponse> {
    const recoveryActionType = this.params.noteType === NoteType.DEVICE ?
        PredefinedMessageType.DEVICE_RECOVERY_ACTION :
        PredefinedMessageType.HOST_RECOVERY_ACTION;
    const errorMessage =
        `Failed to load recovery action for lab ${this.params.labName}`;
    return this.getCommonPredefinedMessagesObservable(
        this.params.labName, recoveryActionType, errorMessage);
  }

  /** Generate basic observable by parameters. */
  getCommonPredefinedMessagesObservable(
      labName: string, messageType: PredefinedMessageType,
      errorMessage: string): Observable<PredefinedMessagesResponse> {
    return this.tfcClient.getPredefinedMessages(labName, messageType)
        .pipe(catchError(err => {
          this.notifier.showError(errorMessage);
          return observableOf(err);
        }));
  }

  /** Adds offline reason options from list of predefined message. */
  setOfflineReasons(messages: PredefinedMessage[]) {
    this.offlineReasons = messages;
    this.filteredOfflineReasons =
        this.forms.get('offlineReasonFormControl')!.valueChanges.pipe(
            startWith(''),
            map(content => content ? this.filter(this.offlineReasons, content) :
                                     this.offlineReasons.slice()));
  }

  /** Setup drop down recovery action options in autocomplete. */
  setRecoveryActions(messages: PredefinedMessage[]) {
    this.recoveryActions = messages;
    this.filteredRecoveryActions =
        this.forms.get('recoveryActionFormControl')!.valueChanges.pipe(
            takeUntil(this.destroy), startWith(''),
            map(content => content ?
                    this.filter(this.recoveryActions, content) :
                    this.recoveryActions.slice()));
  }

  /** Create or update notes for hosts or devices.  */
  saveNotes() {
    if (!this.forms.errors) {
      this.isLoading = true;
      const notesInfo: BatchCreateOrUpdateNotesInfo =
          this.params.noteType === NoteType.DEVICE ?
          this.getBatchCreateOrUpdateNotesInfo(
              this.params.ids, NoteType.DEVICE) :
          this.getBatchCreateOrUpdateNotesInfo(this.params.ids, NoteType.HOST);

      const nonExistingPredefinedMessage =
          this.checkAnyNonExistingPredefinedMessage(notesInfo);
      if (nonExistingPredefinedMessage) {
        const message = 'A new predefined message ' +
            `[${nonExistingPredefinedMessage}] is ` +
            'going to be created with notes.\n' +
            'Are you sure to continue?';
        this.notifier
            .confirm(
                message, 'Creating new PredefinedMessage?', 'Continue', 'Abort')
            .pipe(
                filter(isConfirmed => isConfirmed !== false),
                takeUntil(this.destroy),
                finalize(() => {
                  this.isLoading = false;
                }),
                )
            .subscribe(() => {
              if (this.params.noteType === NoteType.DEVICE) {
                this.batchCreateOrUpdateDevicesNotes(notesInfo);
              } else {
                this.batchCreateOrUpdateHostsNotes(notesInfo);
              }
            });
      } else {
        if (this.params.noteType === NoteType.DEVICE) {
          this.batchCreateOrUpdateDevicesNotes(notesInfo);
        } else {
          this.batchCreateOrUpdateHostsNotes(notesInfo);
        }
      }
    }
    this.startSurvey();
  }

  checkAnyNonExistingPredefinedMessage(noteInfo: BatchCreateOrUpdateNotesInfo):
      string {
    if (!noteInfo.offline_reason_id && noteInfo.offline_reason) {
      return noteInfo.offline_reason;
    }
    if (!noteInfo.recovery_action_id && noteInfo.recovery_action) {
      return noteInfo.recovery_action;
    }
    return '';
  }

  batchCreateOrUpdateDevicesNotes(notesInfo: BatchCreateOrUpdateNotesInfo) {
    this.tfcClient
        .batchCreateOrUpdateDevicesNotesWithPredefinedMessage(notesInfo)
        .pipe(
            takeUntil(this.destroy),
            finalize(() => {
              this.isLoading = false;
            }),
            )
        .subscribe(
            () => {
              const message = this.action === NoteEditorAction.CREATE ?
                  'created' :
                  'updated';
              this.notifier.showMessage(`${NoteType.DEVICE.toLowerCase()} notes
                      ${message}`);
              this.saved.emit(true);
            },
            () => {
              // Error message to display all failed ids.
              this.notifier.showError(`Failed to ${
                  this.action.toLowerCase()} notes for ${
                  NoteType.DEVICE.toLowerCase()} ${
                  notesInfo.notes.map(note => note.device_serial).join(', ')}`);
              this.saved.emit(false);
            },
        );
  }

  batchCreateOrUpdateHostsNotes(notesInfo: BatchCreateOrUpdateNotesInfo) {
    this.tfcClient.batchCreateOrUpdateHostsNotesWithPredefinedMessage(notesInfo)
        .pipe(
            takeUntil(this.destroy),
            finalize(() => {
              this.isLoading = false;
            }),
            )
        .subscribe(
            () => {
              const message = this.action === NoteEditorAction.CREATE ?
                  'created' :
                  'updated';
              this.notifier.showMessage(`${NoteType.HOST.toLowerCase()} notes
                      ${message}`);
              this.saved.emit(true);
            },
            () => {
              // Error message to display all failed ids.
              this.notifier.showError(`Failed to ${
                  this.action.toLowerCase()} notes for ${
                  NoteType.HOST.toLowerCase()} ${
                  notesInfo.notes.map(note => note.hostname).join(', ')}`);
              this.saved.emit(false);
            },
        );
  }

  /**
   * Generate note object for create or update.
   * @param targetsIds Array of hostname or device serial.
   */
  getBatchCreateOrUpdateNotesInfo(targetIds: string[], noteType: NoteType):
      BatchCreateOrUpdateNotesInfo {
    const offlineReasonValue =
        this.forms.get('offlineReasonFormControl')!.value.trim();
    const recoveryActionValue =
        this.forms.get('recoveryActionFormControl')!.value.trim();
    const messageValue = this.forms.get('messageFormControl')!.value.trim();
    const offlineReason =
        this.offlineReasons.find(x => x.content === offlineReasonValue);
    const recoveryAction =
        this.recoveryActions.find(x => x.content === recoveryActionValue);
    const notesObj: BatchCreateOrUpdateNotesInfo = {
      lab_name: this.params.labName,
      message: messageValue,
      notes: targetIds.map(id => {
        const note: Partial<Note> = {
          id: this.params.noteId,
          device_serial: noteType === NoteType.DEVICE ? id : undefined,
          hostname: noteType === NoteType.HOST ?
              id :
              this.getHostnameFromDeviceHostMap(id),
        };
        return note;
      }),
      offline_reason: offlineReasonValue,
      offline_reason_id: offlineReason ? offlineReason.id : undefined,
      recovery_action: recoveryActionValue,
      recovery_action_id: recoveryAction ? recoveryAction.id : undefined,
      event_time: this.eventDateTime ?
          this.eventDateTime.toISOString().slice(0, 19) :
          undefined,
    };
    return notesObj;
  }

  private filter(target: PredefinedMessage[], content: string):
      PredefinedMessage[] {
    const filterValue = content.toLowerCase();
    return target.filter(
        option => option.content.toLowerCase().includes(filterValue));
  }

  getHostnameFromDeviceHostMap(deviceSerial: string): string {
    let hostname = '';
    const deviceHost =
        this.params.deviceHostMap?.find(x => x[0] === deviceSerial);
    hostname = deviceHost ? deviceHost[1] ?? '' : '';
    return hostname;
  }

  /** Switch to note list mode. */
  viewNoteList() {
    this.switchToListMode.emit(true);
  }

  startSurvey() {
    this.feedbackService.startSurvey(SurveyTrigger.NOTES_EDITOR);
  }
}
