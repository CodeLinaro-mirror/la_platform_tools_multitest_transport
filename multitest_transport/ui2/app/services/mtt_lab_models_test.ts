import {DEVICE_COUNT_SUMMARIES, newMockDeviceInfo, newMockHostInfo, newMockHostResource, newMockLabDeviceInfo, newMockLabOfflineHostInfosByLabResponse, newMockUnconvertedHostInfo} from '../testing/mtt_lab_mocks';

import {calculateTotalDeviceCountSummary, convertToLabDeviceInfo, convertToLabHostInfo, convertToLabHostResource, getDeviceSerialForDisplay} from './mtt_lab_models';
import {DeviceType, HostResource, HostState, TestHarness} from './tfc_models';

describe('MttLabModels', () => {
  it('converts to HostInfo correctly when required key is not found', () => {
    const source1 = newMockHostInfo(
        'host45', TestHarness.MH, HostState.RUNNING, false, 'lab-2',
        'host group-2', [{key: 'offline_devices', value: '5'}], undefined, '',
        DEVICE_COUNT_SUMMARIES[2]);
    const source2 = newMockHostInfo(
        'host45', TestHarness.MH, HostState.RUNNING, false, 'lab-2',
        'host group-2', [{key: 'total_devices', value: '10'}], undefined, '',
        DEVICE_COUNT_SUMMARIES[2]);
    const source3 = newMockHostInfo(
        'host45', TestHarness.MH, HostState.RUNNING, false, 'lab-2',
        'host group-2', [{key: 'testkey', value: 'testvalue'}], undefined, '',
        DEVICE_COUNT_SUMMARIES[2]);
    const expectedExtraInfo = {
      allocated_devices: '0',
      available_devices: '0',
      offline_devices: '5',
      total_devices: '10',
      device_count_time_stamp: '',
      host_note_id: 0,
    };
    const expectedResult = newMockUnconvertedHostInfo(
        'host45', TestHarness.MH, HostState.RUNNING, false, 'lab-2',
        'host group-2', expectedExtraInfo, undefined, '',
        DEVICE_COUNT_SUMMARIES[2]);

    const result1 = convertToLabHostInfo(source1);
    expect(result1).toEqual(expectedResult);

    const result2 = convertToLabHostInfo(source2);
    expect(result2).toEqual(expectedResult);

    const result3 = convertToLabHostInfo(source3);
    expectedResult.extraInfo = Object.assign({}, expectedExtraInfo);
    expectedResult.extraInfo['testkey'] = 'testvalue';
    expect(result3).toEqual(expectedResult);
  });

  it('calculates device summary numbers correctly', async () => {
    const lab = 'lab-1';
    const hostInfosResponse = newMockLabOfflineHostInfosByLabResponse(lab);
    const totalDeviceCountSummary =
        calculateTotalDeviceCountSummary(hostInfosResponse.host_infos!);

    expect(totalDeviceCountSummary.allDevices).toEqual(274);
    expect(totalDeviceCountSummary.offlineDevices).toEqual(133);
  });

  it('converts to DeviceInfo correctly', () => {
    const source = newMockDeviceInfo();
    source.extra_info.push({key: 'testkey', value: 'testvalue'});
    const result = convertToLabDeviceInfo(source);

    expect(result.device_serial).toEqual(source.device_serial);
    expect(result.extraInfo['testkey']).toEqual('testvalue');
  });

  it('converts to LabHostResource correctly', () => {
    const source = newMockHostResource('host01');
    const result = convertToLabHostResource(source);

    expect(result?.hostname).toEqual(source.hostname);
    expect(result?.update_timestamp).toEqual(source.update_timestamp);
    expect(result?.event_timestamp).toEqual(source.event_timestamp);
    expect(result?.resource?.identifier).toEqual({'hostname': 'host01'});
    expect(result?.resource?.attribute).toEqual(
        [{'name': 'harness_version', 'value': 'aversion'}]);
    expect(result?.resource?.resource[0].resource_name).toEqual('disk_util');
    expect(result?.resource?.resource[1].resource_name).toEqual('memory');
  });

  it('converts to LabHostResource with empty resource correctly', () => {
    const source: HostResource = {
      hostname: 'ahost'
    };
    const result = convertToLabHostResource(source);

    expect(result).toBeNull();
  });

  it('should return correct serial for display', () => {
    expect(getDeviceSerialForDisplay(newMockLabDeviceInfo('device-1')))
        .toEqual('device-1');

    expect(getDeviceSerialForDisplay({
      ...newMockLabDeviceInfo('device-1'),
      device_type: DeviceType.REMOTE_VIRTUAL,
    })).toEqual('remote-virtual-unknown-unknown');

    expect(getDeviceSerialForDisplay({
      ...newMockLabDeviceInfo('device-1'),
      device_type: DeviceType.REMOTE_VIRTUAL,
      preconfigured_ip: '1.1.1.1',
    })).toEqual('remote-virtual-1.1.1.1-unknown');

    expect(getDeviceSerialForDisplay({
      ...newMockLabDeviceInfo('device-1'),
      device_type: DeviceType.REMOTE_VIRTUAL,
      preconfigured_ip: '1.1.1.1',
      preconfigured_device_num_offset: 2,
    })).toEqual('remote-virtual-1.1.1.1-2');

    expect(getDeviceSerialForDisplay({
      ...newMockLabDeviceInfo('device-1'),
      device_type: DeviceType.LOCAL_VIRTUAL,
      preconfigured_device_num_offset: 0,
    })).toEqual('local-virtual-0');
  });
});
