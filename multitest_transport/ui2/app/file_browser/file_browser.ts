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
import {Component, OnDestroy, OnInit, ViewChild} from '@angular/core';
import {MatTable} from '@angular/material/table';
import {ActivatedRoute, Router, UrlSegment} from '@angular/router';
import {combineLatest, ReplaySubject, Subject} from 'rxjs';
import {filter, finalize, mergeMap, takeUntil} from 'rxjs/operators';

import {encodePath, FileNode, FileService, FileType, humanFileSize, joinPath, PROXY_PATH} from '../services/file_service';
import {Notifier} from '../services/notifier';
import {buildApiErrorMessage, noAwait} from '../shared/util';

/** A component for file browsing */
@Component({
  standalone: false,
  selector: 'file-browser',
  styleUrls: ['file_browser.css'],
  templateUrl: './file_browser.ng.html',
})
export class FileBrowser implements OnInit, OnDestroy {
  readonly encodePath = encodePath;
  readonly FileType = FileType;
  readonly humanFileSize = humanFileSize;
  readonly PROXY_PATH = PROXY_PATH;

  isLoading = false;
  // True if currently uploading a file
  isUploading = false;
  /** File upload completion percentage (0 to 100). */
  uploadProgress = 0;
  // Hold list of files when navigate to or load a directory
  files: FileNode[] = [];
  // Hold information of the current directory path
  currentDirectory: string = '';
  // Host that contains browsing files
  hostname: string = '';

  // Table that displays the list of files
  @ViewChild(MatTable, {static: false}) table!: MatTable<{}>;
  columnsToDisplay = ['name', 'timestamp', 'size', 'action'];

  /** Notified when the component is destroyed. */
  private readonly destroy = new ReplaySubject<void>();
  /** Notified when the cancel upload button is pressed. */
  readonly cancel = new Subject();

  constructor(
      private readonly fs: FileService,
      private readonly route: ActivatedRoute,
      private readonly liveAnnouncer: LiveAnnouncer,
      readonly router: Router,
      private readonly notifier: Notifier,
  ) {}

  ngOnInit() {
    combineLatest([this.route.queryParamMap, this.route.url]).subscribe(res => {
      this.hostname = res[0].get('hostname') || '';
      this.currentDirectory = res[1].map((u: UrlSegment) => u.path).join('/');
      this.loadFiles();
    });
  }

  /**
   * Uploads a file to the local file store, and reload content.
   * @param file file to upload
   */
  async uploadFile(file?: File) {
    if (!file) {
      return;
    }

    this.isUploading = true;
    noAwait(this.liveAnnouncer.announce(`Uploading ${file.name}`, 'polite'));
    this.fs.uploadFile(file, joinPath(this.currentDirectory, file.name))
        .pipe(
            takeUntil(this.destroy),
            takeUntil(this.cancel),
            finalize(() => {
              this.isUploading = false;
              this.uploadProgress = 0;
            }),
            )
        .subscribe(
            event => {
              this.uploadProgress = event.progress;
              if (event.done) {
                this.liveAnnouncer.announce(
                    `${file.name} uploaded`, 'assertive');
                this.loadFiles();
              }
            },
            error => {
              this.notifier.showError(
                  `Failed to upload '${file.name}'.`,
                  buildApiErrorMessage(error));
            });
  }

  navigateToFolder(path: string) {
    this.router.navigate(
        ['/file_browser/' + path],
        {queryParams: this.hostname ? {hostname: this.hostname} : {}});
  }

  ngOnDestroy() {
    this.destroy.next();
  }

  /** Reloads the list of files in the current directory. */
  private loadFiles() {
    this.isLoading = true;
    this.fs.listFiles(this.currentDirectory, this.hostname)
        .pipe(
            takeUntil(this.destroy),
            finalize(() => {
              this.isLoading = false;
            }),
            )
        .subscribe(
            files => {
              this.files = files;
            },
            error => {
              this.notifier.showError(
                  `Failed to load files.`, buildApiErrorMessage(error));
            });
  }

  /**
   * Deletes a local file.
   * @param file to delete
   */
  deleteFile(file: FileNode) {
    this.notifier
        .confirm(`Do you really want to delete '${file.name}'?`, 'Delete File')
        .pipe(
            filter(x => x),
            mergeMap(() => this.fs.deleteFile(file.path, this.hostname)),
            )
        .subscribe(
            () => {
              this.loadFiles();
            },
            error => {
              this.notifier.showError(
                  `Failed to delete file '${file.name}'.`,
                  buildApiErrorMessage(error));
            });
  }
}
