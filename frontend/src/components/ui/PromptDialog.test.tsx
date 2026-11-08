import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { PromptDialog } from './PromptDialog';
import { Modal } from './Modal';

describe('PromptDialog (F-33)', () => {
  it('focuses the input and selects its initial text', () => {
    render(
      <PromptDialog
        open
        title="Rename chat"
        message="New title"
        initialValue="Old name"
        onSubmit={() => {}}
        onCancel={() => {}}
      />,
    );
    const input = screen.getByRole('textbox') as HTMLInputElement;
    expect(document.activeElement).toBe(input);
    expect(input.value).toBe('Old name');
    expect(input.selectionStart).toBe(0);
    expect(input.selectionEnd).toBe('Old name'.length);
  });

  it('submits the typed value and cancels on Escape', () => {
    const onSubmit = vi.fn();
    const onCancel = vi.fn();
    render(
      <PromptDialog open title="Rename" message="Title" initialValue="a" onSubmit={onSubmit} onCancel={onCancel} />,
    );
    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: 'Renamed' } });
    fireEvent.click(screen.getByRole('button', { name: 'OK' }));
    expect(onSubmit).toHaveBeenCalledWith('Renamed');
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onCancel).toHaveBeenCalled();
  });
});

describe('Modal back chevron (F-32)', () => {
  it('shows a Back button when onBack is given and calls it', () => {
    const onBack = vi.fn();
    render(
      <Modal open onClose={() => {}} title="Skills" onBack={onBack}>
        body
      </Modal>,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Back' }));
    expect(onBack).toHaveBeenCalledTimes(1);
  });

  it('has no Back button without onBack', () => {
    render(
      <Modal open onClose={() => {}} title="Top level">
        body
      </Modal>,
    );
    expect(screen.queryByRole('button', { name: 'Back' })).toBeNull();
  });
});
