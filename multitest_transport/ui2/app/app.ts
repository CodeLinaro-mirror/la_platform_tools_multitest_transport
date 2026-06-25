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

import {HTTP_INTERCEPTORS, HttpClientModule} from '@angular/common/http';
import {ChangeDetectionStrategy, Component, Inject, NgModule, OnDestroy, provideZoneChangeDetection} from '@angular/core';
import {MAT_DIALOG_DATA, MatDialog, MatDialogRef} from '@angular/material/dialog';
import {MatTooltipModule} from '@angular/material/tooltip';
import {BrowserModule} from '@angular/platform-browser';
import {BrowserAnimationsModule} from '@angular/platform-browser/animations';
import {mapToCanDeactivate, NavigationEnd, Router, RouterModule, Routes} from '@angular/router';
import {ReplaySubject} from 'rxjs';
import {takeUntil} from 'rxjs/operators';

import {AuthModule} from './auth/auth_module';
import {AuthReturnPage} from './auth/auth_return_page';
import {BuildChannelEditPage} from './build_channels/build_channel_edit_page';
import {BuildChannelList} from './build_channels/build_channel_list';
import {BuildCreatePage} from './builds/build_create_page';
import {BuildDetailPage} from './builds/build_detail_page';
import {BuildListPage} from './builds/build_list_page';
import {ConfigSetList} from './config_sets/config_set_list';
import {ConfigSetPicker} from './config_sets/config_set_picker';
import {DeviceActionEditPage} from './device_actions/device_action_edit_page';
import {DeviceActionList} from './device_actions/device_action_list';
import {DeviceDetailsPage} from './devices/device_details_page';
import {DeviceListPage} from './devices/device_list_page';
import {FileBrowserPage} from './file_browser/file_browser_page';
import {FileCleanerConfigEditPage} from './file_cleaner/file_cleaner_config_edit_page';
import {FileCleanerPolicyEditPage} from './file_cleaner/file_cleaner_policy_edit_page';
import {FileCleanerSettingList} from './file_cleaner/file_cleaner_setting_list';
import {HostDetailsPage} from './hosts/host_details_page';
import {HostListPage} from './hosts/host_list_page';
import {V6IframeContainerComponent} from './shared/v6_iframe_container_component';
import {NotesModule} from './notes/notes_module';
import {AnalyticsInterceptor, AnalyticsService} from './services/analytics_service';
import {APP_DATA, AppData, convertLocalUrl} from './services/app_data';
import {FILE_BROWSER_PATH} from './services/file_service';
import {ServicesModule} from './services/services_module';
import {StrictParamsInterceptor} from './services/strict_params';
import {UserService} from './services/user_service';
import {NotificationsForm} from './settings/notifications_form';
import {SettingForm} from './settings/setting_form';
import {SettingPage} from './settings/setting_page';
import {SetupWizardDialog} from './setup_wizard/setup_wizard_dialog';
import {SetupWizardModule} from './setup_wizard/setup_wizard_module';
import {UnsavedChangeGuard} from './shared/can_deactivate';
import {SharedModule} from './shared/shared_module';
import {EditTestSuitesPage} from './test_plans/edit_test_suites_page';
import {TestPlanEditPage} from './test_plans/test_plan_edit_page';
import {TestPlanListPage} from './test_plans/test_plan_list_page';
import {TestRunActionEditPage} from './test_run_actions/test_run_action_edit_page';
import {TestRunActionList} from './test_run_actions/test_run_action_list';
import {NewTestRunPage} from './test_runs/new_test_run_page';
import {TestRunDetailPage} from './test_runs/test_run_detail_page';
import {TestRunListPage} from './test_runs/test_run_list_page';
import {TestEditPage} from './tests/test_edit_page';
import {TestListPage} from './tests/test_list_page';

/** Routing paths for the sidenav */
export const routes: Routes = [
  {path: 'auth_return', component: AuthReturnPage},
  {path: 'build_channels/new', component: BuildChannelEditPage},
  {
    path: 'build_channels/new',
    component: BuildChannelEditPage,
    canDeactivate: mapToCanDeactivate([UnsavedChangeGuard])
  },
  {
    path: 'build_channels/:id',
    component: BuildChannelEditPage,
    canDeactivate: mapToCanDeactivate([UnsavedChangeGuard])
  },
  {path: 'builds', component: BuildListPage},
  {
    path: 'builds/new',
    component: BuildCreatePage,
    canDeactivate: mapToCanDeactivate([UnsavedChangeGuard])
  },
  {path: 'builds/:id', component: BuildDetailPage},
  {
    path: 'config_sets/add',
    component: ConfigSetPicker,
  },
  {
    path: 'device_actions/new',
    component: DeviceActionEditPage,
    canDeactivate: mapToCanDeactivate([UnsavedChangeGuard])
  },
  {
    path: 'device_actions/new/:copy_id',
    component: DeviceActionEditPage,
    canDeactivate: mapToCanDeactivate([UnsavedChangeGuard])
  },
  {
    path: 'device_actions/view/:view_id',
    component: DeviceActionEditPage,
    canDeactivate: mapToCanDeactivate([UnsavedChangeGuard])
  },
  {
    path: 'device_actions/:id',
    component: DeviceActionEditPage,
    canDeactivate: mapToCanDeactivate([UnsavedChangeGuard])
  },
  {path: 'devices', component: DeviceListPage},
  {path: '', redirectTo: '/test_runs', pathMatch: 'full'},
  {
    path: '',
    component: V6IframeContainerComponent,
    children: [
      {path: 'devices/:id', component: DeviceDetailsPage},
      {path: 'hosts/:id', component: HostDetailsPage},
    ]
  },
  {
    path: 'file_cleaner/policy/new',
    component: FileCleanerPolicyEditPage,
    canDeactivate: mapToCanDeactivate([UnsavedChangeGuard])
  },
  {
    path: 'file_cleaner/policy/:index',
    component: FileCleanerPolicyEditPage,
    canDeactivate: mapToCanDeactivate([UnsavedChangeGuard])
  },
  {
    path: 'file_cleaner/config/new',
    component: FileCleanerConfigEditPage,
    canDeactivate: mapToCanDeactivate([UnsavedChangeGuard])
  },
  {
    path: 'file_cleaner/config/:index',
    component: FileCleanerConfigEditPage,
    canDeactivate: mapToCanDeactivate([UnsavedChangeGuard])
  },
  {path: 'hosts', component: HostListPage},
  {
    path: 'settings',
    component: SettingPage,
    children: [
      {path: 'build_channels', component: BuildChannelList},
      {path: 'config_sets', component: ConfigSetList},
      {path: 'device_actions', component: DeviceActionList},
      {path: 'file_cleaner', component: FileCleanerSettingList},
      {
        path: 'general',
        component: SettingForm,
        canDeactivate: mapToCanDeactivate([UnsavedChangeGuard])
      },
      {
        path: 'notifications',
        component: NotificationsForm,
        canDeactivate: mapToCanDeactivate([UnsavedChangeGuard])
      },
      {path: 'test_run_actions', component: TestRunActionList},
      {path: '**', redirectTo: '/settings/general', pathMatch: 'full'},
    ]
  },
  {path: 'test_plans', component: TestPlanListPage},
  {
    path: 'test_plans/new',
    component: TestPlanEditPage,
    canDeactivate: mapToCanDeactivate([UnsavedChangeGuard])
  },
  {
    path: 'test_plans/edit_test_suites',
    component: EditTestSuitesPage,
  },
  {
    path: 'test_plans/:id',
    component: TestPlanEditPage,
    canDeactivate: mapToCanDeactivate([UnsavedChangeGuard])
  },
  {
    path: 'test_run_actions/new',
    component: TestRunActionEditPage,
    canDeactivate: mapToCanDeactivate([UnsavedChangeGuard])
  },
  {
    path: 'test_run_actions/new/:copy_id',
    component: TestRunActionEditPage,
    canDeactivate: mapToCanDeactivate([UnsavedChangeGuard])
  },
  {
    path: 'test_run_actions/:id',
    component: TestRunActionEditPage,
    canDeactivate: mapToCanDeactivate([UnsavedChangeGuard])
  },
  {path: 'test_runs', component: TestRunListPage},
  {
    path: 'test_runs/new',
    component: NewTestRunPage,
    canDeactivate: mapToCanDeactivate([UnsavedChangeGuard])
  },
  {path: 'test_runs/:id', component: TestRunDetailPage},
  {
    path: FILE_BROWSER_PATH,
    children: [{path: '**', component: FileBrowserPage}]
  },
  {path: 'tests', component: TestListPage},
  {
    path: 'tests/new',
    component: TestEditPage,
    canDeactivate: mapToCanDeactivate([UnsavedChangeGuard])
  },
  {
    path: 'tests/new/:copy_id',
    component: TestEditPage,
    canDeactivate: mapToCanDeactivate([UnsavedChangeGuard])
  },
  {
    path: 'tests/:id',
    component: TestEditPage,
    canDeactivate: mapToCanDeactivate([UnsavedChangeGuard])
  },
  {path: '**', redirectTo: '/test_runs', pathMatch: 'full'},
];

/** Homepage */
@Component(
    {standalone: false, changeDetection: ChangeDetectionStrategy.Eager,
     selector: 'mtt', styleUrls: ['./app.css'], templateUrl: './app.ng.html'})
export class Mtt implements OnDestroy {
  sideNavExpanded = false;
  atsMajorVersionStr = '';
  netdataUrl: string = '';
  dialogRef!: MatDialogRef<SetupWizardDialog>;
  private readonly destroy = new ReplaySubject<void>();

  constructor(
      private readonly analytics: AnalyticsService,
      private readonly dialog: MatDialog,
      private readonly router: Router,
      readonly userService: UserService,
      @Inject(APP_DATA) readonly appData: AppData,
  ) {
    if (!appData.setupWizardCompleted) {
      this.dialogRef = this.dialog.open(SetupWizardDialog, {
        disableClose: true,
        height: '400px',
        panelClass: 'no-padding-container',
        width: '600px',
      });
    }
    if (appData.isOmniLabBased) {
      this.atsMajorVersionStr = 'ATS 2.0';
    } else {
      this.atsMajorVersionStr = 'ATS 1.0';
    }
    if (appData.netdataUrl) {
      this.netdataUrl = convertLocalUrl(appData.netdataUrl, appData.hostname);
    }
    this.initRouteTrackingForAnalytics();
    this.checkUserPermission();
  }

  ngOnDestroy() {
    this.destroy.next();
    this.destroy.complete();
  }

  /** Initialize the tracking of route change events. */
  private initRouteTrackingForAnalytics() {
    this.router.events.subscribe(event => {
      if (event instanceof NavigationEnd) {
        // Determine the route path, i.e. /path/:param instead of /path/123.
        const root = this.router.routerState.snapshot.root.firstChild;
        const paths = [];
        // To support nested routes, iterate over the route tree
        for (let route = root; route; route = route.firstChild) {
          paths.push(route.routeConfig && route.routeConfig.path || '');
        }
        let path = paths ? paths.join('/') : '/';
        // Append the fragment
        const fragment = root && root.fragment;
        if (fragment) {
          path += `#${fragment}`;
        }
        this.analytics.trackLocation(path);
      }
    });
  }

  checkUserPermission() {
    this.userService.checkPermission()
        .pipe(takeUntil(this.destroy))
        .subscribe(
            (result) => {
              this.userService.setAdmin(result.isAdmin);
            },
            () => {
              this.userService.setAdmin(false);
            });
  }

  trackPageView(path: string) {
    this.analytics.trackLocation(path);
  }
}

/** Main module */
@NgModule({
  declarations: [Mtt],
  imports: [
    AuthModule,
    BrowserModule,
    BrowserAnimationsModule,
    HttpClientModule,
    MatTooltipModule,
    NotesModule,
    ServicesModule,
    SetupWizardModule,
    SharedModule,
    RouterModule.forRoot(routes),
  ],
  bootstrap: [Mtt],
  providers: [
    provideZoneChangeDetection(),
    {provide: HTTP_INTERCEPTORS, useClass: AnalyticsInterceptor, multi: true}, {
      provide: HTTP_INTERCEPTORS,
      useClass: StrictParamsInterceptor,  // must be placed after analytics
      multi: true
    },
    {
      provide: APP_DATA,
      // Accessing a global window object.
      // tslint:disable-next-line:no-any
      useValue: (window as any)['APP_DATA'],
    },
    {
      provide: MAT_DIALOG_DATA,
      useValue: {},
    },
    UnsavedChangeGuard
  ],
  })
export class MttModule {
}
