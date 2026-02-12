import {Component, EventEmitter, Input, Output, ChangeDetectionStrategy} from '@angular/core';
import {TableColumn} from 'google3/third_party/py/multitest_transport/ui2/app/services/mtt_models';

/**
 * A button to let users view and select what columns of a table should be
 * shown.
 */
@Component({
  changeDetection: ChangeDetectionStrategy.Eager,standalone: false,
  selector: 'view-columns-button',
  styleUrls: ['view_columns_button.css'],
  templateUrl: './view_columns_button.ng.html',
})
export class ViewColumnsButton {
  @Input() columns: TableColumn[] = [];
  @Output() readonly columnToggled = new EventEmitter<number>();

  toggleColumn(event: Event, columnIndex: number) {
    event.stopPropagation();
    this.columnToggled.emit(columnIndex);
  }
}
