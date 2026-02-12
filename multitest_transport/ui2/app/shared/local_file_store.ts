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
import {Component, EventEmitter, Input, OnDestroy, OnInit, Output, ViewChild, ChangeDetectionStrategy} from '@angular/core';
import {MatTable} from '@angular/material/table';
import {ReplaySubject, Subject} from 'rxjs';
import {filter, finalize, mergeMap, takeUntil} from 'rxjs/operators';

import {FileNode, FileService, FileType, getDirectoryPath, humanFileSize, joinPath} from '../services/file_service';
import {Notifier} from '../services/notifier';

import {buildApiErrorMessage, noAwait} from './util';

// Local file store root directory
const ROOT_DIRECTORY = 'local_file_store';
const ROOT_DIRECTORY_RE = new RegExp(`^${ROOT_DIRECTORY}/`);

/** Displays and manages user-uploaded local files. */
@Component({
  changeDetection: ChangeDetectionStrategy.Eager,standalone: false,
  selector: 'local-file-store',
  styleUrls: ['local_file_store.css'],
  templateUrl: './local_file_store.ng.html',
})
export class LocalFileStore implements OnInit, OnDestroy {
  readonly FileType = FileType;

  @Input() url!: string;
  @Output() readonly urlChange = new EventEmitter<string>();

  @ViewChild(MatTable, {static: false}) table!: MatTable<{}>;
  columnsToDisplay = ['name', 'timestamp', 'size', 'action'];

  /** Notified when the component is destroyed. */
  private readonly destroy = new ReplaySubject<void>();
  /** Notified when the cancel upload button is pressed. */
  readonly cancel = new Subject();

  isLoading = false;
  files: FileNode[] = [];
  selectedFile?: FileNode;
  currentDirectory: string = '';
  /** True if currently uploading a file to local storage. */
  isUploading = false;
  /** File upload completion percentage (0 to 100). */
  uploadProgress = 0;

  constructor(
      private readonly fs: FileService,
      private readonly liveAnnouncer: LiveAnnouncer,
      private readonly notifier: Notifier) {}

  ngOnInit() {
    const path = this.fs.getRelativePathAndHostname(this.url)[0];
    const directory =
        ROOT_DIRECTORY_RE.test(path) ? getDirectoryPath(path) : ROOT_DIRECTORY;
    this.changeDirectory(directory);
  }

  ngOnDestroy() {
    this.destroy.next();
  }

  /** Returns the file path without the root directory prefix. */
  getRelativePath(path: string) {
    return path.replace(ROOT_DIRECTORY_RE, '');
  }

  /**
   * Changes the current directory and reloads the list of files.
   * @param directory directory to change to
   */
  changeDirectory(directory: string|FileNode) {
    this.currentDirectory =
        typeof directory === 'string' ? directory : directory.path;
    this.loadFiles();
  }

  /** Reloads the list of files in the current directory. */
  private loadFiles() {
    this.isLoading = true;
    this.fs.listFiles(this.currentDirectory)
        .pipe(
            takeUntil(this.destroy),
            finalize(() => {
              this.isLoading = false;
            }),
            )
        .subscribe(files => {
          this.files = files;
          // Check if selected file exists
          const path = this.selectedFile ?
              this.selectedFile.path :
              this.fs.getRelativePathAndHostname(this.url)[0];
          const file = this.files.find(
              f => f.path === path && f.type !== FileType.DIRECTORY);
          this.selectFile(file);
        });
  }

  /**
   * Selects a file and generates its URL, or clears the selection.
   * @param file file to select
   */
  selectFile(file?: FileNode) {
    this.selectedFile = file;
    this.urlChange.emit(file ? this.fs.getFileUrl('', file.path) : '');
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

  /**
   * Deletes a local file.
   * @param file to delete
   */
  deleteFile(file: FileNode) {
    this.notifier
        .confirm('Do you really want to delete this file?', 'Delete File')
        .pipe(
            filter(x => x),
            mergeMap(() => this.fs.deleteFile(file.path)),
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

  /** Get human readable file size. */
  getHumanFileSize(size: number): string {
    return humanFileSize(size);
  }
}
