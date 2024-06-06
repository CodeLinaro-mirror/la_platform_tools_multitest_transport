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

import {DebugElement} from '@angular/core';
import {ComponentFixture, fakeAsync, TestBed, tick} from '@angular/core/testing';
import {NoopAnimationsModule} from '@angular/platform-browser/animations';
import {provideRouter} from '@angular/router';
import {of as observableOf, throwError} from 'rxjs';

import {MttClient} from '../services/mtt_client';
import {AuthorizationMethod, AuthorizationState, BuildChannel} from '../services/mtt_models';
import {Notifier} from '../services/notifier';
import {getEl, getTextContent, hasEl} from '../testing/jasmine_util';
import {newMockCredentialsInfo} from '../testing/mtt_mocks';

import {BuildChannelItem} from './build_channel_item';
import {BuildChannelsModule} from './build_channels_module';

describe('BuildChannelItem', () => {
  let mtt: jasmine.SpyObj<MttClient>;
  let notifier: jasmine.SpyObj<Notifier>;

  let component: BuildChannelItem;
  let fixture: ComponentFixture<BuildChannelItem>;
  let element: DebugElement;

  beforeEach(() => {
    notifier = jasmine.createSpyObj(['showError']);
    mtt = jasmine.createSpyObj([
      'authorizeBuildChannel', 'authorizeBuildChannelWithServiceAccount',
      'unauthorizeBuildChannel'
    ]);

    TestBed.configureTestingModule({
      imports: [BuildChannelsModule, NoopAnimationsModule],
      providers: [
        provideRouter([]),
        {provide: MttClient, useValue: mtt},
        {provide: Notifier, useValue: notifier},
      ],
    });

    fixture = TestBed.createComponent(BuildChannelItem);
    element = fixture.debugElement;
    component = fixture.componentInstance;
    spyOn(component.authChange, 'emit');
    spyOn(component.deleteItem, 'emit');
  });

  /** Convenience method to reload a new build channel. */
  function reload(data: Partial<BuildChannel>, editable = true) {
    component.buildChannel = data as BuildChannel;
    component.edit = editable;
    fixture.detectChanges();
  }

  it('can display an authorized build channel', () => {
    reload({
      auth_state: AuthorizationState.AUTHORIZED,
      auth_methods: [AuthorizationMethod.OAUTH2_SERVICE_ACCOUNT],
      credentials: newMockCredentialsInfo(),
    });

    const text = getTextContent(element);
    expect(text).toContain('credentials_email@google.com');
    expect(text).toContain('Use Different Service Account');
    expect(hasEl(element, '.revoke-button')).toBeTruthy();
  });

  it('can display an auth button', () => {
    reload({
      auth_state: AuthorizationState.UNAUTHORIZED,
      auth_methods: [AuthorizationMethod.OAUTH2_SERVICE_ACCOUNT],
    });
    const text = getTextContent(element);
    expect(text).toContain('Upload Service Account Key');
    expect(hasEl(element, '.revoke-button')).toBeFalsy();
  });

  it('can display keyfile button only', () => {
    reload({
      auth_state: AuthorizationState.UNAUTHORIZED,
      auth_methods: [AuthorizationMethod.OAUTH2_SERVICE_ACCOUNT],
    });
    const text = getTextContent(element);
    expect(text).not.toContain('Use Different User Account');
    expect(text).toContain('Upload Service Account Key');
    expect(hasEl(element, '.revoke-button')).toBeFalsy();
  });

  it('can display a build channel without authorization', () => {
    reload({auth_state: AuthorizationState.NOT_APPLICABLE});
    expect(hasEl(element, '.auth-button')).toBeFalsy();
    expect(hasEl(element, '.keyfile-button')).toBeFalsy();
    expect(hasEl(element, '.revoke-button')).toBeFalsy();
  });

  it('can enable editing', () => {
    reload({}, true);
    expect(hasEl(element, '.edit-button')).toBeTruthy();
    expect(hasEl(element, '.delete-button')).toBeTruthy();
  });

  it('can disable editing', () => {
    reload({}, false);
    expect(hasEl(element, '.edit-button')).toBeFalsy();
    expect(hasEl(element, '.delete-button')).toBeFalsy();
  });

  it('can display a default build channel', () => {
    reload({id: 'google_cloud_storage'});  // default GCS build channel
    // can't delete default build channel
    expect(hasEl(element, '.edit-button')).toBeTruthy();
    expect(hasEl(element, '.delete-button')).toBeFalsy();
  });

  it('can delete a build channel', () => {
    reload({id: 'bc_id'});
    getEl(element, '.delete-button').click();
    // notifies parent to delete item
    expect(component.deleteItem.emit)
        .toHaveBeenCalledWith(jasmine.objectContaining({id: 'bc_id'}));
  });

  it('can authorize a build channel with a service account', fakeAsync(() => {
      mtt.authorizeBuildChannelWithServiceAccount.and.returnValue(
//TODO: Wait until b/208710526 is fixed, then remove this autogenerated error suppression.
// @ts-ignore(go/unfork-jasmine-typings): Argument of type 'Observable<null>' is not assignable to parameter of type 'Observable<void>'.
         observableOf(null));
      reload({
       id: 'bc_id',
       auth_state: AuthorizationState.UNAUTHORIZED,
       auth_methods: [AuthorizationMethod.OAUTH2_SERVICE_ACCOUNT],
      });
      const file = new File([], 'file');
      const fileInput = getEl<HTMLInputElement>(element, 'input[type=file]');
//TODO: Wait until b/208710526 is fixed, then remove this autogenerated error suppression.
// @ts-ignore(go/unfork-jasmine-typings): Argument of type 'File[]' is not assignable to parameter of type 'FileList'.
      spyOnProperty(fileInput, 'files').and.returnValue([file]);
      fileInput.dispatchEvent(new Event('change'));  // Select a key file
      tick(500);
      // authorizes build channel and notifies parent
      expect(mtt.authorizeBuildChannelWithServiceAccount)
         .toHaveBeenCalledWith('bc_id', file);
      expect(notifier.showError).not.toHaveBeenCalled();
      expect(component.authChange.emit)
         .toHaveBeenCalledWith(jasmine.objectContaining({id: 'bc_id'}));
    }));

  it('can handle errors when authorizing with a service account', () => {
    mtt.authorizeBuildChannelWithServiceAccount.and.returnValue(
        throwError('authorize failed'));
    reload({
      id: 'bc_id',
      auth_state: AuthorizationState.UNAUTHORIZED,
      auth_methods: [AuthorizationMethod.OAUTH2_SERVICE_ACCOUNT],
    });
    const fileInput = getEl<HTMLInputElement>(element, 'input[type=file]');
//TODO: Wait until b/208710526 is fixed, then remove this autogenerated error suppression.
// @ts-ignore(go/unfork-jasmine-typings): Argument of type 'File[]' is not assignable to parameter of type 'FileList'.
    spyOnProperty(fileInput, 'files').and.returnValue([new File([], 'file')]);
    fileInput.dispatchEvent(new Event('change'));  // Select a key file
    // displays error and doesn't notify parent
    expect(notifier.showError).toHaveBeenCalled();
    expect(component.authChange.emit).not.toHaveBeenCalled();
  });

  it('can revoke a build channel\'s authorization', fakeAsync(() => {
//TODO: Wait until b/208710526 is fixed, then remove this autogenerated error suppression.
// @ts-ignore(go/unfork-jasmine-typings): Argument of type 'Observable<null>' is not assignable to parameter of type 'Observable<void>'.
       mtt.unauthorizeBuildChannel.and.returnValue(observableOf(null));
       reload({
         id: 'bc_id',
         auth_state: AuthorizationState.AUTHORIZED,
         credentials: newMockCredentialsInfo(),
       });
       getEl(element, '.revoke-button').click();
       tick(500);
       // revokes authorization and notifies parent
       expect(mtt.unauthorizeBuildChannel).toHaveBeenCalledWith('bc_id');
       expect(notifier.showError).not.toHaveBeenCalled();
       expect(component.authChange.emit)
           .toHaveBeenCalledWith(jasmine.objectContaining({id: 'bc_id'}));
     }));

  it('can handle errors when revoking authorization', () => {
    mtt.unauthorizeBuildChannel.and.returnValue(
        throwError('unauthorize failed'));
    reload({
      id: 'bc_id',
      auth_state: AuthorizationState.AUTHORIZED,
      credentials: newMockCredentialsInfo(),
    });
    getEl(element, '.revoke-button').click();
    // displays error and doesn't notify parent
    expect(notifier.showError).toHaveBeenCalled();
    expect(component.authChange.emit).not.toHaveBeenCalled();
  });
});
