/**
 * @fileoverview Directives for rows selection on a table.
 */

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

import {SelectionModel} from '@angular/cdk/collections';
import {AfterContentInit, ContentChildren, Directive, EventEmitter, HostListener, Input, OnInit, Output, QueryList} from '@angular/core';
import {assertRequiredInput} from './util';

/**
 * A directive for user to click on a checkbox to selects/deselects the
 * selection of the table. The checkbox is usually next to a row. It should work
 * with tableRowsSelectManager and tableRowSelect directives.
 */
@Directive({
  standalone: false,
  selector: 'mat-checkbox[tableRowSelectCheckbox]',
  exportAs: 'tableRowSelectCheckbox',
})
export class TableRowSelectCheckbox {
  @Input() rowIdFieldValue = '';
  @Input() rowIndex = -1;

  get isSelected() {
    return this.rowsSelectManager.selection.isSelected(this.rowIdFieldValue);
  }

  constructor(public rowsSelectManager: TableRowsSelectManager) {
    assertRequiredInput(
        this.rowsSelectManager, 'rowsSelectManager', 'TableRowSelectCheckbox');
  }

  /** Records if the user selects the row with shift key. */
  @HostListener('click', ['$event'])
  recordRowSelectedEvent(event: MouseEvent) {
    this.rowsSelectManager.recordRowSelectedEvent(event, this.rowIndex);
  }

  /**
   * Toggles the selection and emit the selected hosts when the user clicks on
   * the row.
   */
  @HostListener('change')
  select() {
    this.rowsSelectManager.select(this.rowIndex);
  }
}

/**
 * A directive for user to click on a checkbox to selects/deselects all the
 * selection of the table. The checkbox is usually next to headers at the top.
 * It should work with tableRowsSelectManager directive.
 */
@Directive({
  standalone: false,
  selector: 'mat-checkbox[tableRowsSelectCheckbox]',
  exportAs: 'tableRowsSelectCheckbox',
})
export class TableRowsSelectCheckbox {
  get isAllRowsSelected(): boolean {
    return this.rowsSelectManager.selection.hasValue() &&
        this.rowsSelectManager.isAllSelected();
  }

  get isPartialRowsSelected(): boolean {
    return this.rowsSelectManager.selection.hasValue() &&
        !this.rowsSelectManager.isAllSelected();
  }

  constructor(public rowsSelectManager: TableRowsSelectManager) {
    assertRequiredInput(
        this.rowsSelectManager, 'rowsSelectManager', 'TableRowSelectCheckbox');
  }

  /**
   * Toggles the selection and emit the selected hosts when the user clicks on
   * the row.
   */
  @HostListener('change')
  toggleAllSelection() {
    this.rowsSelectManager.toggleAllSelection();
  }
}

/**
 * A directive for user to click on a row to selects/deselects the selection
 * of the table. It should work with tableRowsSelectManager directive.
 */
@Directive({
  standalone: false,
  selector: '[tableRowSelect]',
  exportAs: 'tableRowSelect',
  host: {
    '[class.selected]':
        'rowsSelectManager.selection.isSelected(rowIdFieldValue)'
  },
})
export class TableRowSelect {
  @Input() rowIdFieldValue = '';
  @Input() rowIndex = -1;

  /** True if the user selects the row with shift key. */
  isSelectedWithShiftKey = false;

  constructor(public rowsSelectManager: TableRowsSelectManager) {
    assertRequiredInput(
        this.rowsSelectManager, 'rowsSelectManager', 'TableRowSelect');
  }

  /** Records if the user selects the row with shift key. */
  recordRowSelectedEvent(event: MouseEvent) {
    this.isSelectedWithShiftKey = !!event.shiftKey;
    event.stopPropagation();
  }

  /**
   * Records if the user selects the row with shift key and toggles the
   * selection when the user clicks on the row.
   */
  @HostListener('click', ['$event'])
  select(event?: MouseEvent) {
    if (event) {
      this.isSelectedWithShiftKey = !!event.shiftKey;
    }
    this.toggleSelection();

    this.rowsSelectManager.prevClickedRowIndex = this.rowIndex;
    this.isSelectedWithShiftKey = false;
  }

  /**
   * Toggles the selection by single or range select and emit the selected
   * rowIdFieldValues.
   */
  toggleSelection() {
    if (this.isSelectedWithShiftKey &&
        this.rowsSelectManager.prevClickedRowIndex >= 0) {
      this.rowsSelectManager.rangeSelect(this.rowIdFieldValue, this.rowIndex);
    } else {
      this.rowsSelectManager.singleSelect(this.rowIdFieldValue);
    }
  }
}

/**
 * A directive that manages rows selection, enables single and range select
 * functionalities. It should work with tableRowSelect directive and can
 * optionally works with tableRowsSelectCheckbox and tableRowSelectCheckbox
 * directives.
 */
@Directive({
  standalone: false,
  selector: '[tableRowsSelectManager]',
  exportAs: 'tableRowsSelectManager',
  host: {'class': 'selectable'},
})
export class TableRowsSelectManager implements OnInit, AfterContentInit {
  @Input() initialSelection: string[] = [];
  @Input() rowIdFieldAllValues: string[] = [];

  @Output() readonly selectionChange = new EventEmitter<string[]>();

  /** The index of a row that was clicked last time. */
  prevClickedRowIndex = -1;

  selection = new SelectionModel<string>(/* allow multi select */ true, []);

  @ContentChildren(TableRowSelect) tableRowSelects!: QueryList<TableRowSelect>;

  ngOnInit() {
    this.selectSelection(this.initialSelection);
  }

  ngAfterContentInit() {
    assertRequiredInput(
        this.tableRowSelects, 'tableRowSelects', 'TableRowsSelectManager');
  }

  /** Records if the user selects the row with shift key. */
  recordRowSelectedEvent(event: MouseEvent, rowIndex: number) {
    this.tableRowSelects.find(
                            x => x.rowIndex ===
                                rowIndex)!.recordRowSelectedEvent(event);
  }

  resetPrevClickedRowIndex() {
    this.prevClickedRowIndex = -1;
  }

  /**
   * Toggles the selection and emit the selected rows when the user clicks on
   * the row.
   */
  select(rowIndex: number) {
    this.tableRowSelects.find(x => x.rowIndex === rowIndex)!.select();
  }

  /** Sets the selected list to empty */
  clearSelection() {
    this.selection.clear();
  }

  /**
   * Selects all rows if they are not all selected; otherwise clear selection.
   */
  toggleAllSelection() {
    this.isAllSelected() ? this.selection.clear() : this.selectAllSelection();
    this.selectionChange.emit(this.selection.selected);
  }

  /**
   * True if the number of selected elements matches the total number of rows.
   */
  isAllSelected(): boolean {
    const numSelected = this.selection.selected.length;
    const numRows = this.rowIdFieldAllValues.length;
    return numSelected === numRows;
  }

  /** Selects all rows. */
  selectAllSelection() {
    this.selection.select(...this.rowIdFieldAllValues);
    this.selectionChange.emit(this.selection.selected);
  }

  /** Selects rows. */
  selectSelection(rowIdFieldValues: string[]) {
    this.selection.select(...rowIdFieldValues);
    this.selectionChange.emit(this.selection.selected);
  }

  /**
   * Resets selected rows to ensure each selected item can be found in the
   * dataSource.
   */
  resetSelection() {
    for (const s of this.selection.selected) {
      if (!this.rowIdFieldAllValues.find(value => value === s)) {
        this.selection.deselect(s);
      }
    }

    this.resetPrevClickedRowIndex();
    this.selectionChange.emit(this.selection.selected);
  }

  /** Toggles a single selection row. */
  singleSelect(rowIdFieldValue: string) {
    this.selection.toggle(rowIdFieldValue);
    this.selectionChange.emit(this.selection.selected);
  }

  /**
   * Toggles the selection values by range. It's used when the user click the
   * row or checkbox with shift key to do range select.
   */
  rangeSelect(rowIdFieldValue: string, rowIndex: number) {
    const {rangeRowStart, rangeRowEnd} = this.getRowRangeIndex(rowIndex);

    // Decides to select or unselect the hosts by range. If the target row is
    // checked already,then the target action will be unselect, and vice versa.
    const isAddSelection = !this.selection.isSelected(rowIdFieldValue);
    const targetRowKeys =
        this.rowIdFieldAllValues.slice(rangeRowStart, rangeRowEnd + 1);

    if (isAddSelection) {
      this.selection.select(...targetRowKeys);
    } else {
      this.selection.deselect(...targetRowKeys);
    }

    this.selectionChange.emit(this.selection.selected);
  }

  /** Calculates and gets the indexes of range. */
  getRowRangeIndex(rowIndex: number):
      {rangeRowStart: number, rangeRowEnd: number} {
    return {
      rangeRowStart: Math.min(rowIndex, this.prevClickedRowIndex),
      rangeRowEnd: Math.max(rowIndex, this.prevClickedRowIndex)
    };
  }
}
