import {DebugElement, SimpleChange} from '@angular/core';
import {ComponentFixture, TestBed} from '@angular/core/testing';
import {NoopAnimationsModule} from '@angular/platform-browser/animations';
import {RouterModule} from '@angular/router';
import {getTextContent} from 'google3/third_party/py/multitest_transport/ui2/app/testing/jasmine_util';
import {DeviceDetailsExtraInfos} from './device_details_extra_infos';
import {DevicesModule} from './devices_module';
import {newMockLabDeviceExtraInfo} from '../testing/mtt_lab_mocks';

describe('DeviceDetailsExtraInfos', () => {
  let deviceDetailsExtraInfos: DeviceDetailsExtraInfos;
  let deviceDetailsExtraInfosFixture: ComponentFixture<DeviceDetailsExtraInfos>;
  let el: DebugElement;
  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [
        DevicesModule,
        NoopAnimationsModule,
        RouterModule,
      ],
    });
    deviceDetailsExtraInfosFixture =
        TestBed.createComponent(DeviceDetailsExtraInfos);
    deviceDetailsExtraInfos = deviceDetailsExtraInfosFixture.componentInstance;
    deviceDetailsExtraInfos.extraInfo = newMockLabDeviceExtraInfo(1);
    deviceDetailsExtraInfos.extraInfoList = (
        deviceDetailsExtraInfos.extraInfoToExtraInfoList(
            deviceDetailsExtraInfos.extraInfo));
    deviceDetailsExtraInfosFixture.detectChanges();
    el = deviceDetailsExtraInfosFixture.debugElement;
  });

  afterEach(() => {
    deviceDetailsExtraInfosFixture.destroy();
  });

  it('should get initialized correctly', () => {
    expect(deviceDetailsExtraInfos).toBeTruthy();
  });

  it('correctly displays a given extra infos', () => {
    deviceDetailsExtraInfos.extraInfo['battery_level'] = 0.123;
    deviceDetailsExtraInfos.extraInfo['testkey'] = 'testvalue';
    deviceDetailsExtraInfos.extraInfoList = (
        deviceDetailsExtraInfos.extraInfoToExtraInfoList(
            deviceDetailsExtraInfos.extraInfo));
    deviceDetailsExtraInfosFixture.detectChanges();
    expect(getTextContent(el)).toContain('testvalue');
    expect(getTextContent(el)).toContain('battery_level');
    expect(getTextContent(el)).toContain('0.123');
  });

  it('sets new values correctly when params changed', () => {
    deviceDetailsExtraInfos.extraInfoList = (
        deviceDetailsExtraInfos.extraInfoToExtraInfoList(
            deviceDetailsExtraInfos.extraInfo));
    deviceDetailsExtraInfosFixture.detectChanges();
    expect(getTextContent(el)).not.toContain('testvalue');

    deviceDetailsExtraInfos.ngOnChanges(
        {extraInfo: new SimpleChange(null, {'testkey': 'testvalue'}, false)});
    deviceDetailsExtraInfosFixture.detectChanges();
    expect(getTextContent(el)).toContain('testvalue');
  });
});
