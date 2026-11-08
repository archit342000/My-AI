import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { ContextMenu, type MenuItem } from './ContextMenu';

const items = (onSelect: () => void): MenuItem[] => [
  { id: 'a', label: 'Rename', onSelect },
  { id: 'b', label: 'Delete', danger: true, onSelect },
];

describe('ContextMenu', () => {
  it('runs the chosen item and closes', async () => {
    const onSelect = vi.fn();
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(<ContextMenu x={10} y={20} items={items(onSelect)} onClose={onClose} />);
    await user.click(screen.getByRole('menuitem', { name: 'Delete' }));
    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('closes on Escape and on outside pointer down, not inside', async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(
      <>
        <span>outside</span>
        <ContextMenu x={0} y={0} items={items(() => undefined)} onClose={onClose} />
      </>,
    );
    await user.click(screen.getByRole('menuitem', { name: 'Rename' }));
    expect(onClose).toHaveBeenCalledTimes(1); // from the item click
    onClose.mockClear();
    fireEvent.pointerDown(screen.getByText('outside'));
    expect(onClose).toHaveBeenCalledTimes(1);
    onClose.mockClear();
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
