import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { useEffect, useState } from 'react';
import { CrudDialog, type FormFooter } from './CrudList';

type Item = { id: string; name: string };
const items: Item[] = [{ id: '1', name: 'Alpha' }, { id: '2', name: 'Beta' }];

function setup(overrides: Partial<Parameters<typeof CrudDialog<Item>>[0]> = {}) {
  const props = {
    open: true,
    onClose: vi.fn(),
    title: 'Things',
    items,
    describe: (i: Item) => ({ id: i.id, title: i.name, subtitle: `id ${i.id}` }),
    renderForm: (initial: Item | null, onDone: () => void) => (
      <div>
        <span>form:{initial?.name ?? 'new'}</span>
        <button onClick={onDone}>done</button>
      </div>
    ),
    onDelete: vi.fn(async () => undefined),
    emptyText: 'Nothing here',
    ...overrides,
  };
  render(<CrudDialog<Item> {...props} />);
  return props;
}

describe('CrudDialog', () => {
  it('lists items with subtitles', () => {
    setup();
    expect(screen.getByText('Alpha')).toBeTruthy();
    expect(screen.getByText('id 2')).toBeTruthy();
  });

  it('shows the empty text when there are no items', () => {
    setup({ items: [] });
    expect(screen.getByText('Nothing here')).toBeTruthy();
  });

  it('Add opens the form with no initial item and done returns to the list', () => {
    setup();
    fireEvent.click(screen.getByRole('button', { name: /Add/ }));
    expect(screen.getByText('form:new')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'done' }));
    expect(screen.getByText('Alpha')).toBeTruthy();
  });

  it('a form gets its own title and a footer with Cancel then Save', () => {
    setup();
    fireEvent.click(screen.getByRole('button', { name: /Add/ }));
    expect(screen.getByRole('heading', { name: 'New item' })).toBeTruthy();
    const footer = document.querySelector('.modal-footer') as HTMLElement;
    expect(Array.from(footer.querySelectorAll('button')).map((b) => b.textContent)).toEqual(['Cancel', 'Save']);
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(screen.getByRole('heading', { name: 'Things' })).toBeTruthy();
    expect(document.querySelector('.modal-footer')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Edit Beta' }));
    expect(screen.getByRole('heading', { name: 'Edit item' })).toBeTruthy();
  });

  it('Escape, the close button and the backdrop return from a form to the list instead of closing the dialog', () => {
    const props = setup();
    const toForm = () => fireEvent.click(screen.getByRole('button', { name: /Add/ }));
    toForm();
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.getByRole('heading', { name: 'Things' })).toBeTruthy();
    toForm();
    fireEvent.click(screen.getByRole('button', { name: 'Close' }));
    expect(screen.getByRole('heading', { name: 'Things' })).toBeTruthy();
    toForm();
    fireEvent.mouseDown(document.querySelector('.modal-backdrop') as HTMLElement);
    expect(screen.getByRole('heading', { name: 'Things' })).toBeTruthy();
    expect(props.onClose).not.toHaveBeenCalled();
    fireEvent.keyDown(document, { key: 'Escape' }); // on the list it closes
    expect(props.onClose).toHaveBeenCalledTimes(1);
  });

  it('a form left open when the dialog is closed from outside is gone when it reopens', () => {
    const base = {
      onClose: vi.fn(),
      title: 'Things',
      items,
      describe: (i: Item) => ({ id: i.id, title: i.name }),
      renderForm: () => <span>the form</span>,
      onDelete: vi.fn(async () => undefined),
      emptyText: 'Nothing here',
    };
    const { rerender } = render(<CrudDialog<Item> {...base} open />);
    fireEvent.click(screen.getByRole('button', { name: /Add/ }));
    expect(screen.getByText('the form')).toBeTruthy();
    rerender(<CrudDialog<Item> {...base} open={false} />);
    rerender(<CrudDialog<Item> {...base} open />);
    expect(screen.queryByText('the form')).toBeNull();
    expect(screen.getByRole('heading', { name: 'Things' })).toBeTruthy();
  });

  it('keeps focus inside the dialog when the view changes (Add, Cancel, Escape)', async () => {
    const dialog = () => document.querySelector('.modal-content') as HTMLElement;
    setup({
      renderForm: (_initial, onDone, footer) => (
        <form id={footer.formId}>
          <input aria-label="field" />
          <button type="button" onClick={onDone}>
            done
          </button>
        </form>
      ),
    });
    fireEvent.click(screen.getByRole('button', { name: /Add/ }));
    await waitFor(() => expect(document.activeElement).toBe(screen.getByLabelText('field')));
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    await waitFor(() => expect(dialog().contains(document.activeElement)).toBe(true));
    expect(document.activeElement).not.toBe(document.body);
    fireEvent.click(screen.getByRole('button', { name: /Add/ }));
    await waitFor(() => expect(document.activeElement).toBe(screen.getByLabelText('field')));
    fireEvent.keyDown(document, { key: 'Escape' });
    await waitFor(() => expect(dialog().contains(document.activeElement)).toBe(true));
    expect(document.activeElement).not.toBe(document.body);
  });

  it('the footer Save submits the form by id and is disabled while the form says it cannot save', () => {
    const onSubmit = vi.fn((e: { preventDefault: () => void }) => e.preventDefault());
    function Form({ footer }: { footer: FormFooter }) {
      const [ok, setOk] = useState(false);
      const { setCanSave } = footer;
      useEffect(() => setCanSave(ok), [ok, setCanSave]);
      return (
        <form id={footer.formId} onSubmit={onSubmit}>
          <button type="button" onClick={() => setOk(true)}>
            make valid
          </button>
        </form>
      );
    }
    setup({ renderForm: (_initial, _onDone, footer) => <Form footer={footer} /> });
    fireEvent.click(screen.getByRole('button', { name: /Add/ }));
    const save = screen.getByRole('button', { name: 'Save' }) as HTMLButtonElement;
    expect(save.disabled).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: 'make valid' }));
    expect(save.disabled).toBe(false);
    fireEvent.click(save);
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });

  it('Edit opens the form pre-filled with that item', () => {
    setup();
    fireEvent.click(screen.getByRole('button', { name: 'Edit Beta' }));
    expect(screen.getByText('form:Beta')).toBeTruthy();
  });

  it('Delete confirms first and then calls onDelete with the item', async () => {
    const props = setup();
    fireEvent.click(screen.getByRole('button', { name: 'Delete Alpha' }));
    expect(screen.getByText(/Delete "Alpha"/)).toBeTruthy();
    expect(props.onDelete).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }));
    await waitFor(() => expect(props.onDelete).toHaveBeenCalledWith(items[0]));
  });

  it('cancelling delete keeps the item', () => {
    const props = setup();
    fireEvent.click(screen.getByRole('button', { name: 'Delete Alpha' }));
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(props.onDelete).not.toHaveBeenCalled();
    expect(screen.getByText('Alpha')).toBeTruthy();
  });

  it('a rejected delete shows an error toast (N6)', async () => {
    const { useToastStore } = await import('../../components/ui/toast-store');
    useToastStore.setState({ toasts: [] });
    const props = setup({ onDelete: vi.fn(async () => { throw new Error('server 500'); }) });
    fireEvent.click(screen.getByRole('button', { name: 'Delete Alpha' }));
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }));
    await waitFor(() => expect(props.onDelete).toHaveBeenCalled());
    await waitFor(() => expect(useToastStore.getState().toasts.some((t) => t.message === 'server 500')).toBe(true));
  });
});
