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

import {Component, OnInit} from '@angular/core';
import {Title} from '@angular/platform-browser';
import {MttClient} from '../services/mtt_client';
import {Notifier} from '../services/notifier';
import {APPLICATION_NAME} from '../shared/shared_module';
import {buildApiErrorMessage, reloadPage} from '../shared/util';
/** A component for display settings */
@Component({
  standalone: false,
  selector: 'setting-page',
  styleUrls: ['setting_page.css'],
  templateUrl: './setting_page.ng.html',
})
export class SettingPage implements OnInit {
  headerTitle = 'Settings';

  navLinks = [
    {path: './general', label: 'General Settings'},
    {path: './config_sets', label: 'Config Sets'},
    {path: './build_channels', label: 'Build Channels'},
    {path: './device_actions', label: 'Device Actions'},
    {path: './test_run_actions', label: 'Test Run Actions'},
    {path: './file_cleaner', label: 'File Cleaner'},
  ];

  constructor(
      private readonly title: Title, private readonly mttClient: MttClient,
      private readonly notifier: Notifier) {}

  ngOnInit() {
    this.title.setTitle(`${APPLICATION_NAME} - ${this.headerTitle}`);
  }

  /**
   * Triggered when import file button is clicked
   * On selecting a file, it will start to upload the file
   * @param file The selected file
   */
  onFileInputChange(file: File|undefined) {
    if (!file) {
      return;
    }
    const reader = new FileReader();

    reader.onloadend = () => {
      // import file contents
      const content = reader.result as string;
      if (!content) {
        this.notifier.showError(
            `Failed to import configuration with empty content`);
        return;
      }
      this.mttClient.importNodeConfig(content).subscribe(
          result => {
            this.notifier.showMessage(`Configuration imported`);
            reloadPage(100);  // Reload all components on the page
          },
          error => {
            this.notifier.showError(
                'Failed to import configuration.', buildApiErrorMessage(error));
          });
    };
    // read contents
    reader.readAsText(file);
  }

  exportNodeConfig() {
    this.mttClient.exportNodeConfig().subscribe(
        result => {
          const element = window.document.createElement('a');
          element.download = 'mtt.yaml';
          element.href = `data:txt/yaml;base64,${btoa(result.value)}`;
          document.body.appendChild(element);
          element.click();
          document.body.removeChild(element);
        },
        error => {
          this.notifier.showError(
              'Failed to export configuration.', buildApiErrorMessage(error));
        });
  }
}
