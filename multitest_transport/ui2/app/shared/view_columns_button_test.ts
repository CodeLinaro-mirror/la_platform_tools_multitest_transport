import {DebugElement} from '@angular/core';
import {ComponentFixture, TestBed} from '@angular/core/testing';
import {NoopAnimationsModule} from '@angular/platform-browser/animations';

import {SharedModule} from './shared_module';
import {ViewColumnsButton} from './view_columns_button';

describe('ViewColumnsButton', () => {
  let viewColumnsButton: ViewColumnsButton;
  let viewColumnsButtonFixture: ComponentFixture<ViewColumnsButton>;
  let el: DebugElement;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [
        NoopAnimationsModule,
        SharedModule,
      ],
    });

    viewColumnsButtonFixture = TestBed.createComponent(ViewColumnsButton);
    el = viewColumnsButtonFixture.debugElement;
    viewColumnsButton = viewColumnsButtonFixture.componentInstance;
    viewColumnsButtonFixture.detectChanges();
  });

  it('initializes a component', () => {
    expect(viewColumnsButton).toBeTruthy();
  });

  it('emits columnToggled event correctly when calling toggleColumn', () => {
    const columnIndex = 2;
    spyOn(viewColumnsButton.columnToggled, 'emit');

    const mockClickEvent = new MouseEvent('click');
    viewColumnsButton.toggleColumn(mockClickEvent, columnIndex);

    expect(viewColumnsButton.columnToggled.emit)
        .toHaveBeenCalledWith(columnIndex);
  });
});
