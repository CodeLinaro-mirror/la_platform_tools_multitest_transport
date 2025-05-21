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

import {HttpClient} from '@angular/common/http';
import {Inject, Injectable, InjectionToken} from '@angular/core';
import {Observable} from 'rxjs';

import {APP_DATA, AppData} from './app_data';
import {TestRun} from './mtt_models';
import {CommandAttempt, isFinalCommandState} from './tfc_models';

/** File server proxy path. */
export const PROXY_PATH = '/fs_proxy';
/** File Browser url path. */
export const FILE_BROWSER_PATH = 'file_browser';

/** Default file upload configuration. */
export const DEFAULT_UPLOAD_CONFIG: FileUploadConfig = {
  initialChunkSize: 4 * 1024 * 1024,  // 4MB
  minChunkSize: 512 * 1024,           // 512KB
  maxChunkSize: 16 * 1024 * 1024,     // 16MB
  minChunkUploadTime: 500,            // 500ms
  maxChunkUploadTime: 2 * 1000,       // 2s
};
/** Injection token for the file upload configuration. */
export const UPLOAD_CONFIG =
    new InjectionToken<FileUploadConfig>('UPLOAD_CONFIG', {
      providedIn: 'root',
      factory: () => DEFAULT_UPLOAD_CONFIG,
    });

/** Performs file operations related to a local file server and its proxy. */
@Injectable({providedIn: 'root'})
export class FileService {
  /** Current upload chunk size, adjusted according to upload time. */
  private chunkSize: number;

  constructor(
      @Inject(APP_DATA) private readonly appData: AppData,
      private readonly http: HttpClient,
      @Inject(UPLOAD_CONFIG) private readonly uploadConfig: FileUploadConfig) {
    this.chunkSize = uploadConfig.initialChunkSize;
  }

  /**
   * Generate an absolute file URL.
   * @param hostname hostname of file url
   * @param parts path substrings
   * @return absolute file URL
   */
  getFileUrl(hostname: string, ...parts: string[]) {
    return joinPath(
        `file://${hostname}${this.appData.fileServerRoot || ''}`, ...parts);
  }

  /**
   * Determine a file URL in a test run attempt's directory.
   * @param testRun relevant test run
   * @param attempt relevant attempt
   * @param path file path relative to the attempt directory
   * @return file URL
   */
  getTestRunFileUrl(testRun: TestRun, attempt: CommandAttempt, path = ''):
      string {
    const outputUrl = testRun.output_url || '';
    if (isFinalCommandState(attempt.state)) {
      // Completed run files are stored in the configured output location.
      if (this.appData.isOmniLabBased) {
        return joinPath(
            outputUrl, attempt.request_id, attempt.command_id, path);
      }
      return joinPath(outputUrl, attempt.command_id, attempt.attempt_id, path);
    }
    if (this.appData.isOmniLabBased) {
      return this.getFileUrl('localhost', path);
    }
    // Active run files are stored in a local temporary location.
    return this.getFileUrl(attempt.hostname, 'tmp', attempt.attempt_id, path);
  }

  /**
   * Get the URL for the test run's merged report root directory.
   * @param testRun relevant test run
   * @return dir URL
   */
  getTestRunMergedReportDirUrl(testRun: TestRun): string {
    const outputUrl = testRun.output_url || '';
    return joinPath(outputUrl, 'merged_report');
  }

  /**
   * Generate a URL at which the directory can be browsed.
   * @param dirUrl directory URL to browse
   * @return directory browse URL
   */
  getFileBrowseUrl(dirUrl: string): string {
    const [relativePath, hostname] = this.getRelativePathAndHostname(dirUrl);
    return joinPath(FILE_BROWSER_PATH, relativePath) +
        `?hostname=${hostname || ''}`;
  }

  /**
   * Generate a URL at which the file can be opened.
   * @param fileUrl file URL to open
   * @return file open URL
   */
  getFileOpenUrl(fileUrl: string): string {
    const [relativePath, hostname] = this.getRelativePathAndHostname(fileUrl);
    return joinPath(PROXY_PATH, 'file', encodePath(relativePath)) +
        `?hostname=${hostname || ''}`;
  }

  /**
   * Determine the file path relative to the file server root.
   * @param fileUrl file URL to relativize
   * @return relative file path
   */
  getRelativePathAndHostname(fileUrl: string): [string, string] {
    let hostname = '';
    try {
      hostname = new URL(fileUrl).hostname;
    } catch {
    }

    const fileServerRoot =
        `file://([^/]+)?${this.appData.fileServerRoot || ''}`;
    fileUrl = fileUrl.replace(new RegExp(`^${fileServerRoot}/?`), '');
    return [fileUrl, hostname];
  }

  /**
   * List all the files in a local directory.
   * @param path directory relative to the file server root
   * @param hostname host of the browsing files
   * @return list of file nodes
   */
  listFiles(path: string, hostname?: string): Observable<FileNode[]> {
    if (hostname) {
      return this.http.get<FileNode[]>(
          `${PROXY_PATH}/dir/${encodePath(path)}?hostname=${hostname}`);
    }
    return this.http.get<FileNode[]>(`${PROXY_PATH}/dir/${encodePath(path)}`);
  }

  /**
   * Upload a file to local storage with adaptive chunk sizes.
   * @param file file to upload
   * @param path destination relative to file server root
   * @return upload progress events
   */
  uploadFile(file: Blob, path: string): Observable<FileUploadEvent> {
    const self = this;
    let cancelled = false;

    return new Observable<FileUploadEvent>(observer => {
      function readChunk(startByte: number) {
        if (cancelled) {
          return;
        }
        const reader = new FileReader();
        const endByte = startByte + self.chunkSize;
        const startTime = Date.now();
        const chunk = file.slice(startByte, endByte);
        reader.onloadend = () => {
          if (reader.error) {
            observer.error(reader.error);
            return;
          }
          const data = reader.result as ArrayBuffer;
          self.uploadChunk(data, path, startByte, file.size)
              .subscribe(
                  () => {
                    if (endByte >= file.size) {
                      observer.next(new FileUploadEvent(file, file.size));
                      observer.complete();
                    } else {
                      observer.next(new FileUploadEvent(file, endByte));
                      const uploadTime = Date.now() - startTime;
                      self.adjustChunkSize(uploadTime);
                      readChunk(endByte);
                    }
                  },
                  error => {
                    observer.error(error);
                  });
        };
        reader.readAsArrayBuffer(chunk);
      }

      readChunk(0);
      return () => cancelled = true;
    });
  }

  /** Adjust chunk size depending on the latest chunk upload time. */
  private adjustChunkSize(uploadTime: number) {
    if (uploadTime < this.uploadConfig.minChunkUploadTime) {
      this.chunkSize =
          Math.min(this.chunkSize * 2, this.uploadConfig.maxChunkSize);
    } else if (uploadTime > this.uploadConfig.maxChunkUploadTime) {
      this.chunkSize =
          Math.max(this.chunkSize / 2, this.uploadConfig.minChunkSize);
    }
  }

  /** Upload a single file chunk. */
  private uploadChunk(
      data: ArrayBuffer, path: string, startByte: number,
      totalSize: number): Observable<void> {
    const headers: {[header: string]: string} = {};
    // Zero-byte files can't have a content range header
    if (data.byteLength > 0) {
      const endByte = Math.min(totalSize, startByte + data.byteLength) - 1;
      headers['Content-Range'] = `bytes ${startByte}-${endByte}/${totalSize}`;
    }
    return this.http.put<void>(
        `${PROXY_PATH}/file/${encodePath(path)}`, data, {headers});
  }

  /**
   * Delete a file from local storage.
   * @param path path relative to the file server root
   * @param hostname host of the browsing files
   */
  deleteFile(path: string, hostname?: string): Observable<void> {
    if (hostname) {
      return this.http.delete<void>(
          `${PROXY_PATH}/file/${encodePath(path)}?hostname=${hostname}`);
    }
    return this.http.delete<void>(`${PROXY_PATH}/file/${encodePath(path)}`);
  }
}

/** File types. */
export enum FileType {
  DIRECTORY = 'DIRECTORY',  // Directory
  FILE = 'FILE',            // Regular file
  OTHER = 'OTHER',          // Other type (e.g. symlink, special device)
}

/** File node model returned from directory list API. */
// tslint:disable:enforce-name-casing
export interface FileNode {
  path: string;         // Relative file path
  name: string;         // File name
  type: FileType;       // File type
  size: number;         // File size (bytes)
  access_time: number;  // Last access timestamp (epoch millis)
  update_time: number;  // Last update timestamp (epoch millis)
}
// tslint:enable:enforce-name-casing

/** File upload configuration, used to determine the chunk size. */
export interface FileUploadConfig {
  readonly initialChunkSize: number;
  readonly minChunkSize: number;
  readonly maxChunkSize: number;
  readonly minChunkUploadTime: number;
  readonly maxChunkUploadTime: number;
}

/** File upload progress event. */
export class FileUploadEvent {
  readonly done: boolean;
  readonly progress: number;

  constructor(readonly file: Blob, readonly uploaded: number) {
    this.done = uploaded === file.size;
    this.progress = this.done ? 100 : uploaded / Math.max(file.size, 1) * 100;
  }
}

/** Encode the segments of a file path. */
export function encodePath(path: string): string {
  return path.split('/').map(encodeURIComponent).join('/');
}

/** Join multiple file path substrings. */
export function joinPath(...parts: string[]): string {
  // Remove empty segments, remove leading/trailing slashes, and join.
  return parts.filter(Boolean).map(p => p.replace(/^\/|\/$/g, '')).join('/');
}

/** Returns the directory path, i.e. everything before the last "/". */
export function getDirectoryPath(path: string): string {
  const index = path.lastIndexOf('/');
  return index === 0 ? '/' : path.substring(0, index);
}

/** Read a blob as text. */
export function readBlobAsText(blob: Blob): Promise<string> {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      resolve(reader.result as string);
    };
    reader.onerror = () => {
      reject(reader.error);
    };
    reader.readAsText(blob);
  });
}

/** Convert file size in bytes to human readble string. */
export function humanFileSize(size: number): string {
  const thresh = 1000;
  const units = ['B', 'kB', 'MB', 'GB', 'TB', 'PB'];
  if (size === 0) {
    return '0 B';
  }
  const i = Math.floor(Math.log(size) / Math.log(thresh));
  const value = Number((size / Math.pow(thresh, i)).toFixed(1));
  return `${value} ${units[i]}`;
}
