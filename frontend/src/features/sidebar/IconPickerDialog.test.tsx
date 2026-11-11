import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { IconPickerDialog } from './IconPickerDialog';

let afterEachCleanup: () => void = () => undefined;
const pressed = (name: string) => screen.getByRole('button', { name }).getAttribute('aria-pressed');

describe('IconPickerDialog', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    afterEachCleanup();
    afterEachCleanup = () => undefined;
  });

  it('a tap chooses, and only Save keeps it', () => {
    const onPick = vi.fn();
    render(<IconPickerDialog open current="star" onPick={onPick} onCancel={() => undefined} />);
    expect(pressed('Star')).toBe('true');
    fireEvent.click(screen.getByRole('button', { name: 'Rocket' }));
    expect(pressed('Rocket')).toBe('true');
    expect(pressed('Star')).toBe('false');
    expect(onPick).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    expect(onPick).toHaveBeenCalledWith('rocket');
  });

  it('Save with nothing chosen changes nothing, so an older icon is kept as it is', () => {
    const onPick = vi.fn();
    const onCancel = vi.fn();
    render(<IconPickerDialog open current="🚀" onPick={onPick} onCancel={onCancel} />);
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    expect(onPick).not.toHaveBeenCalled();
    expect(onCancel).toHaveBeenCalled();
  });

  it('Cancel keeps nothing', () => {
    const onPick = vi.fn();
    const onCancel = vi.fn();
    render(<IconPickerDialog open current="star" onPick={onPick} onCancel={onCancel} />);
    fireEvent.click(screen.getByRole('button', { name: 'Rocket' }));
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(onCancel).toHaveBeenCalled();
    expect(onPick).not.toHaveBeenCalled();
  });

  it('"Back to the folder" returns to the starting icon, saved as no icon of its own', () => {
    const onPick = vi.fn();
    render(<IconPickerDialog open current="star" onPick={onPick} onCancel={() => undefined} />);
    fireEvent.click(screen.getByRole('button', { name: 'Back to the folder' }));
    expect(pressed('Folder')).toBe('true');
    expect(screen.getByRole('button', { name: 'Back to the folder' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    expect(onPick).toHaveBeenCalledWith(null);
  });

  it('a workspace without an icon, or with one that no longer exists, starts on the folder', () => {
    const { unmount } = render(
      <IconPickerDialog open current={null} onPick={() => undefined} onCancel={() => undefined} />,
    );
    expect(pressed('Folder')).toBe('true');
    unmount();
    render(
      <IconPickerDialog open current="gone" onPick={() => undefined} onCancel={() => undefined} />,
    );
    expect(pressed('Folder')).toBe('true');
  });

  it('icons are named in plain words, and the current one is brought into view', () => {
    const scroll = vi.fn();
    // jsdom has no scrollIntoView: give it one for this test.
    Element.prototype.scrollIntoView = scroll;
    afterEachCleanup = () => Reflect.deleteProperty(Element.prototype, 'scrollIntoView');
    render(
      <IconPickerDialog
        open
        current="help-circle"
        onPick={() => undefined}
        onCancel={() => undefined}
      />,
    );
    expect(pressed('Help circle')).toBe('true');
    expect(scroll).toHaveBeenCalled();
  });
});
