import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { IconPickerDialog } from './IconPickerDialog';

let afterEachCleanup: () => void = () => undefined;

describe('IconPickerDialog', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    afterEachCleanup();
    afterEachCleanup = () => undefined;
  });

  it('marks the current icon as pressed and picks another by click', () => {
    const onPick = vi.fn();
    render(<IconPickerDialog open current="folder" onPick={onPick} onCancel={() => undefined} />);
    expect(screen.getByRole('button', { name: 'folder' }).getAttribute('aria-pressed')).toBe(
      'true',
    );
    const other = screen
      .getAllByRole('button')
      .find((b) => b.getAttribute('aria-pressed') === 'false' && b.title);
    fireEvent.click(other as HTMLElement);
    expect(onPick).toHaveBeenCalledWith(other?.title);
  });

  it('"Remove icon" is in the dialog footer and clears the icon', () => {
    const onPick = vi.fn();
    const { baseElement } = render(
      <IconPickerDialog open current="folder" onPick={onPick} onCancel={() => undefined} />,
    );
    const remove = screen.getByRole('button', { name: 'Remove icon' });
    expect(baseElement.querySelector('.modal-footer')?.contains(remove)).toBe(true);
    fireEvent.click(remove);
    expect(onPick).toHaveBeenCalledWith(null);
  });

  it('brings the current icon into view when it opens', () => {
    const scroll = vi.fn();
    // jsdom has no scrollIntoView: give it one for this test.
    Element.prototype.scrollIntoView = scroll;
    afterEachCleanup = () => Reflect.deleteProperty(Element.prototype, 'scrollIntoView');
    render(
      <IconPickerDialog
        open
        current="folder"
        onPick={() => undefined}
        onCancel={() => undefined}
      />,
    );
    expect(scroll).toHaveBeenCalled();
  });
});
