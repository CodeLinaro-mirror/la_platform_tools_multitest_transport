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
import {DebugElement} from '@angular/core';
import {ComponentFixture, TestBed} from '@angular/core/testing';
import {NoopAnimationsModule} from '@angular/platform-browser/animations';
import {provideRouter} from '@angular/router';
import {of as observableOf, throwError} from 'rxjs';

import {MttClient, TestRunActionClient} from '../services/mtt_client';
import {AuthorizationState, TestRunAction} from '../services/mtt_models';
import {Notifier} from '../services/notifier';
import {getEl, getEls, hasEl} from '../testing/jasmine_util';

import {TestRunActionList} from './test_run_action_list';
import {TestRunActionsModule} from './test_run_actions_module';

describe('TestRunActionList', () => {
  let liveAnnouncer: jasmine.SpyObj<LiveAnnouncer>;
  let notifier: jasmine.SpyObj<Notifier>;
  let client: jasmine.SpyObj<TestRunActionClient>;

  let fixture: ComponentFixture<TestRunActionList>;
  let element: DebugElement;
  let component: TestRunActionList;

  beforeEach(() => {
    liveAnnouncer = jasmine.createSpyObj(['announce', 'clear']);
    notifier = jasmine.createSpyObj(['confirm', 'showError', 'showMessage']);
    client = jasmine.createSpyObj([
      'list', 'authorize', 'authorizeWithServiceAccount', 'unauthorize',
      'delete'
    ]);
    client.list.and.returnValue(observableOf([]));
    client.authorize.and.returnValue(observableOf(undefined));
    client.authorizeWithServiceAccount.and.returnValue(observableOf(undefined));
    client.unauthorize.and.returnValue(observableOf(undefined));
    client.delete.and.returnValue(observableOf(undefined));

    TestBed.configureTestingModule({
      imports: [NoopAnimationsModule, TestRunActionsModule],
      providers: [
        provideRouter([]),
        {provide: LiveAnnouncer, useValue: liveAnnouncer},
        {provide: Notifier, useValue: notifier},
        {provide: MttClient, useValue: {testRunActions: client}},
      ],
    });

    fixture = TestBed.createComponent(TestRunActionList);
    fixture.detectChanges();
    element = fixture.debugElement;
    component = fixture.componentInstance;
  });

  /** Convenience method to reload a new set of actions. */
  function reload(configs: Array<Partial<TestRunAction>>) {
    client.list.and.returnValue(observableOf(configs as TestRunAction[]));
    component.load();
    fixture.detectChanges();
  }

  it('can initialize the component', () => {
    expect(component).toBeTruthy();
    expect(client.list).toHaveBeenCalled();
    expect(notifier.showError).not.toHaveBeenCalled();
  });

  it('can announce loading start and end', () => {
    expect(liveAnnouncer.announce).toHaveBeenCalledWith('Loading', 'polite');
    expect(liveAnnouncer.announce)
        .toHaveBeenCalledWith('Test run actions loaded', 'assertive');
  });

  it('can detect that no actions were loaded', () => {
    expect(hasEl(element, 'mat-card')).toBeFalsy();
    expect(hasEl(element, '.empty')).toBeTruthy();
  });

  it('can display a list of actions', () => {
    reload([{name: 'Action #1'}, {name: 'Action #2'}]);
    const cards = getEls(element, 'mat-card');
    expect(cards.length).toBe(2);
    expect(cards[0].textContent).toContain('Action #1');
    expect(cards[1].textContent).toContain('Action #2');
    expect(hasEl(element, '.empty')).toBeFalsy();
  });

  it('can handle errors when loading actions', () => {
    client.list.and.returnValue(throwError('loading failed'));
    component.load();
    expect(notifier.showError).toHaveBeenCalled();
  });

  it('can display an authorized action', () => {
    reload([{authorization_state: AuthorizationState.AUTHORIZED}]);
    const statusButton = getEl(element, 'mat-card status-button');
    expect(statusButton.textContent).toContain('Authorized');
    expect(hasEl(element, 'mat-card #auth-button')).toBeFalsy();
    expect(hasEl(element, 'mat-card #keyfile-button')).toBeFalsy();
    expect(hasEl(element, 'mat-card #revoke-button')).toBeTruthy();
  });

  it('can display an unauthorized action', () => {
    reload([{authorization_state: AuthorizationState.UNAUTHORIZED}]);
    const statusButton = getEl(element, 'mat-card status-button');
    expect(statusButton.textContent).toContain('Unauthorized');
    expect(hasEl(element, 'mat-card #auth-button')).toBeTruthy();
    expect(hasEl(element, 'mat-card #keyfile-button')).toBeTruthy();
    expect(hasEl(element, 'mat-card #revoke-button')).toBeFalsy();
  });

  it('can display an action without authorization', () => {
    reload([{authorization_state: AuthorizationState.NOT_APPLICABLE}]);
    expect(hasEl(element, 'mat-card status-button')).toBeFalsy();
    expect(hasEl(element, 'mat-card #auth-button')).toBeFalsy();
    expect(hasEl(element, 'mat-card #keyfile-button')).toBeFalsy();
    expect(hasEl(element, 'mat-card #revoke-button')).toBeFalsy();
  });

  it('can authorize an action', () => {
    reload([
      {id: 'action_id', authorization_state: AuthorizationState.UNAUTHORIZED}
    ]);
    getEl(element, 'mat-card #auth-button').click();
    expect(client.authorize).toHaveBeenCalledWith('action_id');
    expect(notifier.showError).not.toHaveBeenCalled();
  });

  it('can handle errors when authorizing an action', () => {
    client.authorize.and.returnValue(throwError('authorize failed'));
    reload([
      {id: 'action_id', authorization_state: AuthorizationState.UNAUTHORIZED}
    ]);
    getEl(element, 'mat-card #auth-button').click();
    expect(notifier.showError).toHaveBeenCalled();
  });

  it('can authorize an action with a service account', () => {
    reload([
      {id: 'action_id', authorization_state: AuthorizationState.UNAUTHORIZED}
    ]);
    const file = new File([], 'file');
    const fileInput =
        getEl<HTMLInputElement>(element, 'mat-card input[type=file]');
    spyOnProperty(fileInput, 'files').and.returnValue([file] as unknown as FileList);
    fileInput.dispatchEvent(new Event('change'));  // Select a key file
    expect(client.authorizeWithServiceAccount)
        .toHaveBeenCalledWith('action_id', file);
    expect(notifier.showError).not.toHaveBeenCalled();
  });

  it('can handle errors when authorizing with a service account', () => {
    client.authorizeWithServiceAccount.and.returnValue(
        throwError('authorize failed'));
    reload([
      {id: 'action_id', authorization_state: AuthorizationState.UNAUTHORIZED}
    ]);
    const fileInput =
        getEl<HTMLInputElement>(element, 'mat-card input[type=file]');
    spyOnProperty(fileInput, 'files').and.returnValue([new File([], 'file')] as unknown as FileList);
    fileInput.dispatchEvent(new Event('change'));  // Select a key file
    expect(notifier.showError).toHaveBeenCalled();
  });

  it('can revoke an action\'s authorization', () => {
    reload([
      {id: 'action_id', authorization_state: AuthorizationState.AUTHORIZED}
    ]);
    getEl(element, 'mat-card #revoke-button').click();
    expect(client.unauthorize).toHaveBeenCalledWith('action_id');
    expect(notifier.showError).not.toHaveBeenCalled();
  });

  it('can handle errors when revoking an action\'s authorization', () => {
    client.unauthorize.and.returnValue(throwError('unauthorize failed'));
    reload([
      {id: 'action_id', authorization_state: AuthorizationState.AUTHORIZED}
    ]);
    getEl(element, 'mat-card #revoke-button').click();
    expect(notifier.showError).toHaveBeenCalled();
  });

  it('can delete an action', () => {
    notifier.confirm.and.returnValue(observableOf(true));  // confirm delete
    reload([{id: 'action_id'}]);
    getEl(element, 'mat-card #delete-button').click();
    expect(client.delete).toHaveBeenCalledWith('action_id');
    expect(component.actions).toEqual([]);  // action removed
    expect(notifier.showError).not.toHaveBeenCalled();
  });

  it('can confirm deleting an action', () => {
    notifier.confirm.and.returnValue(observableOf(false));  // cancel delete
    reload([{id: 'action_id'}]);
    getEl(element, 'mat-card #delete-button').click();
    expect(client.delete).not.toHaveBeenCalledWith('action_id');
  });

  it('can handle errors when deleting an action', () => {
    client.delete.and.returnValue(throwError('delete failed'));
    notifier.confirm.and.returnValue(observableOf(true));  // confirm delete
    reload([{id: 'action_id'}]);
    getEl(element, 'mat-card #delete-button').click();
    expect(notifier.showError).toHaveBeenCalled();
  });
});
