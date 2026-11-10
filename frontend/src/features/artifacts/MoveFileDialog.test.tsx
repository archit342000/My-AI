import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { MoveFileDialog } from './MoveFileDialog';

const base = {
  open: true,
  fileName: 'a.md',
  currentFolder: '',
  folders: ['notes', 'notes/2026'],
  onCancel: () => undefined,
};

describe('MoveFileDialog', () => {
  it('Move is disabled until another folder is chosen, then moves there', () => {
    const onMove = vi.fn();
    render(<MoveFileDialog {...base} onMove={onMove} />);
    const move = screen.getByRole('button', { name: 'Move' });
    expect(move).toBeDisabled();
    fireEvent.click(screen.getByRole('combobox', { name: 'Destination folder' }));
    fireEvent.click(screen.getByRole('option', { name: 'notes/2026' }));
    expect(move).toBeEnabled();
    fireEvent.click(move);
    expect(onMove).toHaveBeenCalledWith('notes/2026');
  });

  it('offers the top level as a destination for a file in a folder', () => {
    const onMove = vi.fn();
    render(<MoveFileDialog {...base} currentFolder="notes" onMove={onMove} />);
    fireEvent.click(screen.getByRole('combobox', { name: 'Destination folder' }));
    fireEvent.click(screen.getByRole('option', { name: 'Top level' }));
    fireEvent.click(screen.getByRole('button', { name: 'Move' }));
    expect(onMove).toHaveBeenCalledWith('');
  });

  it('Cancel closes without moving', () => {
    const onCancel = vi.fn();
    const onMove = vi.fn();
    render(<MoveFileDialog {...base} onMove={onMove} onCancel={onCancel} />);
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(onCancel).toHaveBeenCalled();
    expect(onMove).not.toHaveBeenCalled();
  });
});
