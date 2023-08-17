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

import {Component, EventEmitter, Input, OnChanges, OnInit, Output, SimpleChanges, ViewChild} from '@angular/core';
import {MatSelect} from '@angular/material/select';
import {assertRequiredInput} from 'google3/third_party/py/multitest_transport/ui2/app/shared/util';

import {ALL_OPTIONS_VALUE} from '../services/mtt_lab_models';

/** Store value and display status from component input. */
export interface MultiSelectItem {
  value: string;
  hidden: boolean;
}

/**
 * The component is composed of mat-select and a text input for filter options
 * in the selector, and a mat-checkbox to select or deselect all options and
 * filtered options. It is used to select multiple options from a long list.
 */
@Component({
  selector: 'multi-select',
  styleUrls: ['multi_select.css'],
  templateUrl: './multi_select.ng.html',
})
export class MultiSelect implements OnInit, OnChanges {
  @Input() items: string[] = [];
  @Input() inputSelection: string[] = [];
  @Input() itemName = 'item';
  @Input() placeholder = '';
  @Input() formWidth = '300px';
  @Input() appearance: 'fill'|'outline' = 'fill';
  @Input() disabled = false;
  @Output() readonly selectionChange = new EventEmitter<string[]>();
  @Output() readonly keydown = new EventEmitter<KeyboardEvent>();

  @ViewChild(MatSelect, {static: true}) matSelect!: MatSelect;

  selection: string[] = [];
  filterText = '';
  multiSelectItems: MultiSelectItem[] = [];

  /**
   * A selection value converted from the actual selection items.
   * e.g. If the actual selection is the all items in this.multiSelectItems, the
   * converted selection should be ['All'] instead.
   */
  get convertedSelection(): string[] {
    return this.selection.length === this.multiSelectItems.length ?
        [ALL_OPTIONS_VALUE] :
        this.selection;
  }

  ngOnInit() {
    assertRequiredInput(this.items, 'items', 'MultiSelector');
    assertRequiredInput(this.selection, 'selection', 'MultiSelector');
    assertRequiredInput(this.matSelect, 'matSelect', 'MultiSelector');
  }

  ngOnChanges(changes: SimpleChanges) {
    if (changes['items']) {
      this.initMultiSelectItems();
    }
    if (changes['inputSelection']) {
      this.formalizeSelection(this.inputSelection);
    }
  }

  /**
   * Formalizes the input selection as actual items existed in
   * this.multiSelectItems.
   * e.g. If inputSelection is ['All'], the actual
   * selection should be the all items in this.multiSelectItems.
   */
  formalizeSelection(inputSelection: string[]) {
    this.selection = (inputSelection.length === 1 &&
                      inputSelection[0] === ALL_OPTIONS_VALUE) ?
        this.multiSelectItems.map(item => item.value) :
        inputSelection;
  }

  initMultiSelectItems() {
    this.multiSelectItems = this.items.map((item) => {
      const multiSelectItem: MultiSelectItem = {
        value: item,
        hidden: false,
      };
      return multiSelectItem;
    });
  }

  isAllSelected() {
    return this.selection.length === this.multiSelectItems.length;
  }

  isAllFilteredSelected(): boolean {
    let allSelected = true;
    for (const item of this.filteredItems()) {
      if (!this.selection.includes(item.value)) {
        allSelected = false;
        break;
      }
    }
    return allSelected;
  }

  toggleAllSelection(isChecked: boolean) {
    this.selection = isChecked ? [ALL_OPTIONS_VALUE] : [];
    this.selectionChange.emit(this.selection);
  }

  /** Toggle current filtered selections. */
  toggleFilteredSelection() {
    if (this.isAllFilteredSelected()) {
      const filteredSelectedItem = this.filteredSetectedItems();
      this.selection =
          this.selection.filter(item => !filteredSelectedItem.includes(item));
    } else {
      this.selection = this.multiSelectItems
                           .filter((item) => {
                             return item.hidden === false ||
                                 this.selection.includes(item.value);
                           })
                           .map(item => item.value);
    }
    this.selectionChange.emit(this.convertedSelection);
  }

  /** Updates options in drop down if there is text in filter input. */
  doFilter() {
    if (this.filterText) {
      this.multiSelectItems = this.multiSelectItems.map((item) => {
        item.hidden = !(item.value.includes(this.filterText));
        return item;
      });
    } else {
      this.multiSelectItems = this.multiSelectItems.map((item) => {
        item.hidden = false;
        return item;
      });
    }
  }

  /** Gets all filtered items. */
  filteredItems(): MultiSelectItem[] {
    return this.multiSelectItems.filter(item => item.hidden === false);
  }

  /** Gets all selected filtered items. */
  filteredSetectedItems(): string[] {
    const filteredItemsValue = this.filteredItems().map(item => item.value);
    return this.selection.filter(item => {
      return filteredItemsValue.includes(item);
    });
  }

  /** Clears filter input and refresh options in drop down. */
  clearFilter() {
    this.filterText = '';
    this.doFilter();
  }

  filterKeydown(event: KeyboardEvent) {
    event.stopPropagation();
    this.keydown.emit(event);
  }
}
