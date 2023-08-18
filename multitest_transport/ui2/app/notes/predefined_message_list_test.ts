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

import {HttpClientTestingModule} from '@angular/common/http/testing';
import {ComponentFixture, TestBed} from '@angular/core/testing';
import {MatDialog} from '@angular/material/dialog';
import {SortDirection} from '@angular/material/sort';
import {NoopAnimationsModule} from '@angular/platform-browser/animations';
import {of as observableOf} from 'rxjs';

import {MessageCategory, MessageType} from '../services/mtt_lab_models';
import {Notifier} from '../services/notifier';
import {TfcClient} from '../services/tfc_client';
import {PredefinedMessageType} from '../services/tfc_models';
import {newMockLabInfosResponse, newMockPredefinedMessage, newMockPredefinedMessagesResponse} from '../testing/mtt_lab_mocks';

import {NotesModule} from './notes_module';
import {FilterParams, PredefinedMessageList} from './predefined_message_list';

describe('Predefined Message List', () => {
  let predefinedMessageList: PredefinedMessageList;
  let predefinedMessageListFixture: ComponentFixture<PredefinedMessageList>;
  const labInfosResponse = newMockLabInfosResponse();
  const predefinedMessagesResponse = newMockPredefinedMessagesResponse(
      PredefinedMessageType.DEVICE_OFFLINE_REASON);
  const predefinedMessageId =
      predefinedMessagesResponse.predefined_messages![0].id;
  const deletedPredefinedMessage =
      newMockPredefinedMessage(predefinedMessageId);

  let notifierSpy: jasmine.SpyObj<Notifier>;
  let tfcClientSpy: jasmine.SpyObj<TfcClient>;

  beforeEach(() => {
    tfcClientSpy = jasmine.createSpyObj('tfcClient', {
      deletePredefinedMessage: observableOf(deletedPredefinedMessage),
      getLabInfos: observableOf(labInfosResponse),
      getPredefinedMessages: observableOf(predefinedMessagesResponse),
    });

    notifierSpy = jasmine.createSpyObj('notifier', {
      confirm: observableOf(true),  // mock confirm click in dialog.
      showMessage: observableOf({}),
      showError: observableOf({}),
    });

    TestBed.configureTestingModule({
      imports: [
        HttpClientTestingModule,
        NoopAnimationsModule,
        NotesModule,
      ],
      providers: [
        {provide: Notifier, useValue: notifierSpy},
        {provide: TfcClient, useValue: tfcClientSpy},
      ],

    });
    predefinedMessageListFixture =
        TestBed.createComponent(PredefinedMessageList);
    predefinedMessageList = predefinedMessageListFixture.componentInstance;
    predefinedMessageListFixture.detectChanges();
  });

  it('initializes a component', () => {
    expect(predefinedMessageList).toBeTruthy();
  });

  it('calls getLabInfos api when the component loaded', async () => {
    await predefinedMessageListFixture.whenStable();
    expect(tfcClientSpy.getLabInfos).toHaveBeenCalledTimes(1);
  });

  it('saves last filter criteria into localStorage correctly', async () => {
    await predefinedMessageListFixture.whenStable();
    const mockSelectedLab = 'lab-2';
    const mockSelectedMessageCategory = MessageCategory.HOST;
    const mockSelectedMessageType = MessageType.RECOVERY_ACTION;

    predefinedMessageList.selectedLab = mockSelectedLab;
    predefinedMessageList.selectedMessageCategory = mockSelectedMessageCategory;
    predefinedMessageList.selectedMessageType = mockSelectedMessageType;
    predefinedMessageList.updateLocalStorage();

    const storedText = window.localStorage.getItem(
        predefinedMessageList.FILTER_CRITERIA_STORAGE_KEY);

    const storedObject =
        storedText ? (JSON.parse(storedText) as FilterParams) : null;

    expect(storedObject).toEqual({
      lab: mockSelectedLab,
      messageCategory: mockSelectedMessageCategory,
      messageType: mockSelectedMessageType,
    });
  });

  it('gets filter criteria from local storage correctly', async () => {
    await predefinedMessageListFixture.whenStable();
    const mockSelectedLab = 'lab-2';
    const mockSelectedMessageCategory = MessageCategory.HOST;
    const mockSelectedMessageType = MessageType.RECOVERY_ACTION;

    predefinedMessageList.selectedLab = mockSelectedLab;
    predefinedMessageList.selectedMessageCategory = mockSelectedMessageCategory;
    predefinedMessageList.selectedMessageType = mockSelectedMessageType;
    predefinedMessageList.updateLocalStorage();

    const storedData = predefinedMessageList.loadFromLocalStorage();

    expect(storedData).toEqual({
      lab: mockSelectedLab,
      messageCategory: mockSelectedMessageCategory,
      messageType: mockSelectedMessageType,
    });
  });

  it('loads predefined message list correctly', async () => {
    const predefinedMessageTypes = Object.values(PredefinedMessageType);

    for (const type of predefinedMessageTypes) {
      const predefinedMessageResponse = newMockPredefinedMessagesResponse(type);
      tfcClientSpy.getPredefinedMessages.and.returnValue(
          observableOf(predefinedMessageResponse));
      TestBed.inject(TfcClient, tfcClientSpy);

      predefinedMessageList.reloadPredefinedMessages();
      expect(predefinedMessageList.dataSource)
          .toEqual(predefinedMessageResponse.predefined_messages!);
    }
  });

  it('determines current predefined message type correctly', () => {
    // Device offline reason
    predefinedMessageList.selectedMessageCategory = MessageCategory.DEVICE;
    predefinedMessageList.selectedMessageType = MessageType.OFFLINE_REASON;
    expect(predefinedMessageList.getCurrentPredefinedMessageType())
        .toEqual(PredefinedMessageType.DEVICE_OFFLINE_REASON);
    // Device recovery action
    predefinedMessageList.selectedMessageCategory = MessageCategory.DEVICE;
    predefinedMessageList.selectedMessageType = MessageType.RECOVERY_ACTION;
    expect(predefinedMessageList.getCurrentPredefinedMessageType())
        .toEqual(PredefinedMessageType.DEVICE_RECOVERY_ACTION);
    // Host offline reason
    predefinedMessageList.selectedMessageCategory = MessageCategory.HOST;
    predefinedMessageList.selectedMessageType = MessageType.OFFLINE_REASON;
    expect(predefinedMessageList.getCurrentPredefinedMessageType())
        .toEqual(PredefinedMessageType.HOST_OFFLINE_REASON);
    // Host recovery action
    predefinedMessageList.selectedMessageCategory = MessageCategory.HOST;
    predefinedMessageList.selectedMessageType = MessageType.RECOVERY_ACTION;
    expect(predefinedMessageList.getCurrentPredefinedMessageType())
        .toEqual(PredefinedMessageType.HOST_RECOVERY_ACTION);
  });

  it('delete predefined message correctly', async () => {
    await predefinedMessageListFixture.whenStable();

    // Checks the number of predefined message before delete one.
    expect(predefinedMessageList.dataSource.length)
        .toEqual(predefinedMessagesResponse.predefined_messages!.length);

    // Deletes one predefined message.
    predefinedMessageList.deletePredefinedMessage(predefinedMessageId);
    expect(tfcClientSpy.deletePredefinedMessage).toHaveBeenCalledTimes(1);
    expect(tfcClientSpy.deletePredefinedMessage)
        .toHaveBeenCalledWith(predefinedMessageId);

    // Checks the number of predefined message after delete one.
    expect(predefinedMessageList.dataSource.length)
        .toEqual(predefinedMessagesResponse.predefined_messages!.length - 1);
  });

  it('should open editor dialog on openPredefinedMessagesEditor called', () => {
    const dialog = TestBed.inject(MatDialog);
    spyOn(dialog, 'open').and.callThrough();
    predefinedMessageList.openPredefinedMessagesEditor();
    expect(dialog.open).toHaveBeenCalled();
  });

  it('can sort correctly', () => {
    const sortColumn = 'used_count';
    const sortDirection: SortDirection = 'desc';
    const sort = {active: sortColumn, direction: sortDirection};
    predefinedMessageList.changeSort(sort);
    expect(predefinedMessageList.matSort.active).toEqual(sortColumn);
    expect(predefinedMessageList.matSort.direction).toEqual(sortDirection);
  });

  it('editor should close on create success correctly', () => {
    const createId = 2;
    const outputPredefinedMessage = newMockPredefinedMessage(createId);

    const onCreate = predefinedMessageList.editorCloseHandler();

    onCreate(outputPredefinedMessage);

    const createdData = predefinedMessageList.tableDataSource.data.find(
        (x) => x.id === outputPredefinedMessage.id);

    expect(createdData!.id).toEqual(createId);
  });

  it('editor should close on update success correctly', () => {
    const inputPredefinedMessage = newMockPredefinedMessage(1);
    const updateContent = 'updated content text';
    const outputPredefinedMessage = newMockPredefinedMessage(
        1, 'lab1', PredefinedMessageType.DEVICE_OFFLINE_REASON, updateContent);

    const onUpdate =
        predefinedMessageList.editorCloseHandler(inputPredefinedMessage);

    onUpdate(outputPredefinedMessage);

    const updatedData = predefinedMessageList.tableDataSource.data.find(
        (x) => x.id === outputPredefinedMessage.id);

    expect(updatedData!.content).toEqual(updateContent);
  });
});
