import {Component, Input, OnChanges, OnInit, SimpleChanges, ChangeDetectionStrategy} from '@angular/core';
import {assertRequiredInput} from 'google3/third_party/py/multitest_transport/ui2/app/shared/util';
import {LabDeviceExtraInfo} from '../services/mtt_lab_models';


/** Displays extra info list of a device. */
@Component({
  changeDetection: ChangeDetectionStrategy.Eager,standalone: false,
  selector: 'device-details-extra-infos',
  styleUrls: ['device_details_extra_infos.css'],
  templateUrl: 'device_details_extra_infos.ng.html',
})
export class DeviceDetailsExtraInfos implements OnChanges, OnInit {
  @Input() extraInfo!: LabDeviceExtraInfo;
  extraInfoList: ReadonlyArray<{key: string, value: string|number}> = [];

  displayedColumns: string[] = ['key', 'value'];

  ngOnChanges(changes: SimpleChanges) {
    if (changes['extraInfo']) {
      this.extraInfo = changes['extraInfo'].currentValue;
      this.extraInfoList = this.extraInfoToExtraInfoList(this.extraInfo);
    }
  }

  ngOnInit() {
    assertRequiredInput(
        this.extraInfo, 'extraInfo', 'device-details-extra-infos');
    this.extraInfoList = this.extraInfoToExtraInfoList(this.extraInfo);
  }

  /**
   * LabDeviceExtraInfo object to a list of key value pairs.
   * @param extraInfo a LabDeviceExtraInfo
   */
  extraInfoToExtraInfoList(extraInfo: LabDeviceExtraInfo):
      Array<{key: string, value: string|number}> {
    if (!extraInfo) {
      return [];
    }
    return Object.entries(extraInfo).map(o => ({key: o[0], value: o[1]}));
  }
}
