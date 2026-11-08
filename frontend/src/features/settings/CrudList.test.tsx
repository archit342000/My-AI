import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { CrudDialog } from './CrudList';

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
