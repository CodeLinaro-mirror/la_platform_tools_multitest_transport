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
import {of as observableOf, throwError} from 'rxjs';
import {toArray} from 'rxjs/operators';

import {AppData} from './app_data';
import {DEFAULT_UPLOAD_CONFIG, encodePath, FILE_BROWSER_PATH, FileNode, FileService, FileType, getDirectoryPath, joinPath, PROXY_PATH} from './file_service';
import {TestRun, TestRunState} from './mtt_models';
import {CommandAttempt, CommandState} from './tfc_models';

describe('FileService', () => {
  const appData: AppData = {
    fileServerRoot: '/root',
  };
  let http: jasmine.SpyObj<HttpClient>;
  let fs: FileService;

  beforeEach(() => {
    http = jasmine.createSpyObj<HttpClient>(['get', 'put', 'delete']);
    fs = new FileService(appData, http, DEFAULT_UPLOAD_CONFIG);
  });

  it('can get file URL for active attempts', () => {
    const testRun = {} as TestRun;
    const attempt = {
      command_id: 'command_id',
      attempt_id: 'attempt_id',
      state: CommandState.RUNNING,
      hostname: 'hostname',
    } as CommandAttempt;
    const path = 'path/to/file';
    const expected = 'file://hostname/root/tmp/attempt_id/path/to/file';
    expect(fs.getTestRunFileUrl(testRun, attempt, path)).toEqual(expected);
  });

  it('can get file URL for completed attempts', () => {
    const testRun = {output_url: 'output_url'} as TestRun;
    const attempt = {
      command_id: 'command_id',
      attempt_id: 'attempt_id',
      state: CommandState.COMPLETED,
      hostname: 'hostname',
    } as CommandAttempt;
    const path = 'path/to/file';
    const expected = 'output_url/command_id/attempt_id/path/to/file';
    expect(fs.getTestRunFileUrl(testRun, attempt, path)).toEqual(expected);
  });

  it('can get file URL for Omnilab attempts', () => {
    const newAppData: AppData = {
      fileServerRoot: '/root',
      isOmniLabBased: true,
    };
    fs = new FileService(newAppData, http, DEFAULT_UPLOAD_CONFIG);
    const testRun:
        TestRun = {output_url: 'output_url', state: TestRunState.COMPLETED};
    const attempt: CommandAttempt = {
      command_id: 'command_id',
      attempt_id: 'attempt_id',
      request_id: 'request_id',
      state: CommandState.COMPLETED,
      hostname: 'hostname',
    };
    const path = 'path/to/file';
    const expected =
        'output_url/request_id/command_id/tradefed_logs/XtsTradefedTest_test_attempt_id/path/to/file';
    expect(fs.getTestRunFileUrl(testRun, attempt, path)).toEqual(expected);
  });


  it('can get file browse URL for absolute file URLs', () => {
    const url = 'file:///root/path/to/file';
    const expected = `${FILE_BROWSER_PATH}/path/to/file?hostname=`;
    expect(fs.getFileBrowseUrl(url)).toEqual(expected);
  });

  it('can get correct file browse URL without hostname', () => {
    const url = 'file:///root/path/to/file';
    const expected = `${FILE_BROWSER_PATH}/path/to/file?hostname=`;
    expect(fs.getFileBrowseUrl(url)).toEqual(expected);
  });

  it('can get correct file browse URL with hostname', () => {
    const url = 'file://hostname/root/path/to/file';
    const expected = `${FILE_BROWSER_PATH}/path/to/file?hostname=hostname`;
    expect(fs.getFileBrowseUrl(url)).toEqual(expected);
  });

  it('can get file browse URL for relative file paths', () => {
    const path = 'path/to/file';
    const expected = `${FILE_BROWSER_PATH}/path/to/file?hostname=`;
    expect(fs.getFileBrowseUrl(path)).toEqual(expected);
  });

  it('can get file open URL for absolute file URLs', () => {
    const url = 'file:///root/path/to/file';
    const expected = `${PROXY_PATH.slice(1)}/file/path/to/file?hostname=`;
    expect(fs.getFileOpenUrl(url)).toEqual(expected);
  });

  it('can get correct file open URL without hostname', () => {
    const url = 'file:///root/path/to/file';
    const expected = `${PROXY_PATH.slice(1)}/file/path/to/file?hostname=`;
    expect(fs.getFileOpenUrl(url)).toEqual(expected);
  });

  it('can get correct file open URL with hostname', () => {
    const url = 'file://hostname/root/path/to/file';
    const expected =
        `${PROXY_PATH.slice(1)}/file/path/to/file?hostname=hostname`;
    expect(fs.getFileOpenUrl(url)).toEqual(expected);
  });

  it('can get file open URL for relative file paths', () => {
    const path = 'path/to/file';
    const expected = `${PROXY_PATH.slice(1)}/file/path/to/file?hostname=`;
    expect(fs.getFileOpenUrl(path)).toEqual(expected);
  });

  it('can list files in a directory', done => {
    const node: FileNode = {
      path: 'path',
      name: 'name',
      type: FileType.OTHER,
      size: 1,
      access_time: 2,
      update_time: 3,
    };
    http.get.and.returnValue(observableOf([node]));

    fs.listFiles('path').subscribe(result => {
      expect(result).toEqual([node]);
      expect(http.get).toHaveBeenCalledWith(PROXY_PATH + '/dir/path');
      done();
    });
  });

  it('can upload an entire file', done => {
    const file = new Blob(['test']);
    http.put.and.returnValue(observableOf(null));

    fs.uploadFile(file, 'path').pipe(toArray()).subscribe(events => {
      // Sent in a single request
      expect(events.length).toEqual(1);
      expect(events[0].done).toBeTruthy();
      expect(events[0].progress).toEqual(100);
      expect(events[0].uploaded).toEqual(4);  // 4 bytes uploaded
      expect(http.put).toHaveBeenCalledWith(
          PROXY_PATH + '/file/path', bufferOf('test'),
          jasmine.objectContaining(
              {headers: {'Content-Range': 'bytes 0-3/4'}}));
      done();
    });
  });

  it('can upload an empty file', done => {
    const file = new Blob([]);
    http.put.and.returnValue(observableOf(null));

    fs.uploadFile(file, 'path').pipe(toArray()).subscribe(events => {
      // Sent in a single request
      expect(events.length).toEqual(1);
      expect(events[0].done).toBeTruthy();
      expect(events[0].progress).toEqual(100);  // Avoid divide by zero
      expect(events[0].uploaded).toEqual(0);    // No data uploaded
      expect(http.put).toHaveBeenCalledWith(
          PROXY_PATH + '/file/path', bufferOf(''),
          jasmine.objectContaining({headers: {}}));  // No content-range
      done();
    });
  });

  it('can upload a file in chunks', done => {
    const file = new Blob(['chunk test']);
    fs = new FileService(appData, http, {
      initialChunkSize: 4,
      minChunkSize: 2,
      maxChunkSize: 8,
      minChunkUploadTime: Number.MIN_SAFE_INTEGER,  // Upload time never lower
      maxChunkUploadTime: Number.MAX_SAFE_INTEGER,  // Upload time never higher
    });
    http.put.and.returnValue(observableOf(null));

    fs.uploadFile(file, 'path').pipe(toArray()).subscribe(events => {
      expect(events.length).toEqual(3);
      // First request sends first 4 characters
      expect(events[0].done).toBeFalsy();
      expect(events[0].progress).toEqual(40);
      expect(events[0].uploaded).toEqual(4);
      expect(http.put).toHaveBeenCalledWith(
          PROXY_PATH + '/file/path', bufferOf('chun'),
          jasmine.objectContaining(
              {headers: {'Content-Range': 'bytes 0-3/10'}}));
      // Second request has next four characters (no chunk size adjustment)
      expect(events[1].done).toBeFalsy();
      expect(events[1].progress).toEqual(80);
      expect(events[1].uploaded).toEqual(8);
      expect(http.put).toHaveBeenCalledWith(
          PROXY_PATH + '/file/path', bufferOf('k te'),
          jasmine.objectContaining(
              {headers: {'Content-Range': 'bytes 4-7/10'}}));
      // Third request has the remaining content
      expect(events[2].done).toBeTruthy();
      expect(events[2].progress).toEqual(100);
      expect(events[2].uploaded).toEqual(10);
      expect(http.put).toHaveBeenCalledWith(
          PROXY_PATH + '/file/path', bufferOf('st'),
          jasmine.objectContaining(
              {headers: {'Content-Range': 'bytes 8-9/10'}}));
      done();
    });
  });

  it('should increase chunk size if upload is fast', done => {
    const file = new Blob(['x'.repeat(22)]);
    fs = new FileService(appData, http, {
      initialChunkSize: 2,
      minChunkSize: 2,
      maxChunkSize: 8,
      minChunkUploadTime: Number.MAX_SAFE_INTEGER,  // Upload time always lower
      maxChunkUploadTime: Number.MAX_SAFE_INTEGER,
    });
    http.put.and.returnValue(observableOf(null));

    fs.uploadFile(file, 'path').pipe(toArray()).subscribe(events => {
      expect(events.length).toEqual(4);
      expect(events[0].uploaded).toEqual(2);   // initial chunk size of 2
      expect(events[1].uploaded).toEqual(6);   // chunk size doubled to 4
      expect(events[2].uploaded).toEqual(14);  // chunk size capped at 8
      expect(events[3].uploaded).toEqual(22);  // chunk size capped at 8
      done();
    });
  });

  it('should decrease chunk size if upload is slow', done => {
    const file = new Blob(['x'.repeat(16)]);
    fs = new FileService(appData, http, {
      initialChunkSize: 8,
      minChunkSize: 2,
      maxChunkSize: 8,
      minChunkUploadTime: Number.MIN_SAFE_INTEGER,
      maxChunkUploadTime: Number.MIN_SAFE_INTEGER,  // Upload time always higher
    });
    http.put.and.returnValue(observableOf(null));

    fs.uploadFile(file, 'path').pipe(toArray()).subscribe(events => {
      expect(events.length).toEqual(4);
      expect(events[0].uploaded).toEqual(8);   // initial chunk size of 8
      expect(events[1].uploaded).toEqual(12);  // chunk size reduced to 4
      expect(events[2].uploaded).toEqual(14);  // chunk size capped at 2
      expect(events[3].uploaded).toEqual(16);  // chunk size capped at 2
      done();
    });
  });

  it('can handle upload errors', done => {
    const file = new Blob(['test']);
    http.put.and.returnValue(throwError(new Error()));

    fs.uploadFile(file, 'path')
        .subscribe(
            event => {
              fail(`Unexpected upload event: ${event}`);
            },
            error => {
              expect(error).toBeDefined();
              done();
            });
  });

  it('can handle read errors', done => {
    const file = new Blob(['test']);
    // tslint:disable-next-line:no-any replace FileReader for testing
    spyOn(window as any, 'FileReader').and.returnValue(new FailingFileReader());

    fs.uploadFile(file, 'path')
        .subscribe(
            event => {
              fail(`Unexpected upload event: ${event}`);
            },
            error => {
              expect(error).toBeDefined();
              done();
            });
  });

  it('can delete a file', done => {
    http.delete.and.returnValue(observableOf(null));
    fs.deleteFile('path').subscribe(() => {
      expect(http.delete).toHaveBeenCalledWith(PROXY_PATH + '/file/path');
      done();
    });
  });
});

describe('encodePath', () => {
  it('should encode the path segments', () => {
    expect(encodePath('/one/two')).toBe('/one/two');
    expect(encodePath('/o n&e/t#w@o')).toBe('/o%20n%26e/t%23w%40o');
  });
});

describe('joinPath', () => {
  it('can handle a single path substring', () => {
    expect(joinPath('one/two')).toBe('one/two');
  });

  it('can handle paths without leading/trailing slashes', () => {
    expect(joinPath('one/two', 'three/four')).toBe('one/two/three/four');
  });

  it('can handle paths with leading/trailing slashes', () => {
    expect(joinPath('one/two/', '/three/four')).toBe('one/two/three/four');
  });
});

describe('getDirectoryPath', () => {
  it('should return the directory path', () => {
    expect(getDirectoryPath('')).toBe('');
    expect(getDirectoryPath('file')).toBe('');
    expect(getDirectoryPath('/')).toBe('/');
    expect(getDirectoryPath('/file')).toBe('/');
    expect(getDirectoryPath('/dir/')).toBe('/dir');
    expect(getDirectoryPath('/dir/file')).toBe('/dir');
  });
});

/** Custom matcher for testing ArrayBuffer contents. */
function bufferOf(expected: string): jasmine.AsymmetricMatcher<ArrayBuffer> {
  return {
    asymmetricMatch: (actual: ArrayBuffer) =>
        new TextDecoder().decode(actual) === expected,
    jasmineToString: () => `<bufferOf(${expected}) matcher>`,
  };
}

/** File reader which will always have an error. */
class FailingFileReader extends FileReader {
  override get error() {
    return new DOMException();
  }
}
