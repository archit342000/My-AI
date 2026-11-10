import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { HelpDialog } from './HelpDialog';
import { slashCommandsFor } from './slash';

const commands = slashCommandsFor([
  { id: 's1', name: 'summarise', description: 'Summarise a document', instructions: 'x' } as never,
]);

describe('HelpDialog', () => {
  it('lists the built-in commands and each skill with its description', () => {
    render(<HelpDialog open onClose={() => undefined} commands={commands} />);
    const dialog = screen.getByRole('dialog', { name: 'Commands and skills' });
    for (const text of [
      '/help',
      '/skills',
      '/summarise',
      'Summarise a document',
      'Manage custom skills',
    ]) {
      expect(dialog.textContent).toContain(text);
    }
  });

  it('shows nothing while closed, and Escape closes it', () => {
    const onClose = vi.fn();
    const { rerender } = render(<HelpDialog open={false} onClose={onClose} commands={commands} />);
    expect(screen.queryByRole('dialog')).toBeNull();
    rerender(<HelpDialog open onClose={onClose} commands={commands} />);
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalled();
  });
});
