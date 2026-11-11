import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { useEffect, useState } from 'react';
import { useToastStore } from '../../components/ui/toast-store';
import { CrudList, type FormFooter } from './CrudList';

type Item = { id: string; name: string };
const items: Item[] = [
  { id: '1', name: 'Alpha' },
  { id: '2', name: 'Beta' },
];

function setup(overrides: Partial<Parameters<typeof CrudList<Item>>[0]> = {}) {
  const props = {
    noun: 'thing',
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
  render(<CrudList<Item> {...props} />);
  return props;
}
const confirmDelete = () =>
  fireEvent.click(
    within(screen.getByRole('dialog', { name: 'Delete this thing?' })).getByRole('button', {
      name: 'Delete thing',
    }),
  );

describe('CrudList', () => {
  it('lists items with subtitles, a tag and a typewriter title when asked', () => {
    setup({
      describe: (i) => ({
        id: i.id,
        title: i.name,
        subtitle: `id ${i.id}`,
        tag: 'style',
        mono: true,
      }),
    });
    expect(screen.getByText('Alpha').className).toContain('font-mono');
    expect(screen.getByText('id 2')).toBeTruthy();
    expect(screen.getAllByText('style')).toHaveLength(2);
  });

  it('shows the toolbar above the list and says nothing matches while it is filtering', () => {
    setup({ items: [], filtering: true, toolbar: <input aria-label="search" /> });
    expect(screen.getByLabelText('search')).toBeTruthy();
    expect(screen.getByText('Nothing matches.')).toBeTruthy();
    expect(screen.queryByText('Nothing here')).toBeNull();
  });

  it('shows the empty text when there are no items, and says so while loading instead', () => {
    const { unmount } = render(
      <CrudList<Item>
        noun="thing"
        items={[]}
        describe={(i) => ({ id: i.id, title: i.name })}
        renderForm={() => null}
        onDelete={async () => undefined}
        emptyText="Nothing here"
      />,
    );
    expect(screen.getByText('Nothing here')).toBeTruthy();
    unmount();
    setup({ items: [], loading: true });
    expect(screen.queryByText('Nothing here')).toBeNull();
    expect(screen.getByRole('status')).toHaveTextContent('Loading');
  });

  it('"New thing" opens the form in place, under the list that stays; done closes it', () => {
    setup();
    fireEvent.click(screen.getByRole('button', { name: 'New thing' }));
    expect(screen.getByRole('group', { name: 'New thing' })).toHaveTextContent('form:new');
    expect(screen.getByText('Alpha')).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'New thing' })).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'done' }));
    expect(screen.queryByRole('group', { name: 'New thing' })).toBeNull();
    expect(screen.getByRole('button', { name: 'New thing' })).toBeTruthy();
  });

  it('the form ends with Cancel then Save, and Cancel closes it', () => {
    setup();
    fireEvent.click(screen.getByRole('button', { name: 'New thing' }));
    const form = screen.getByRole('group', { name: 'New thing' });
    const foot = form.querySelector('.crud-form__foot') as HTMLElement;
    expect(Array.from(foot.querySelectorAll('button')).map((b) => b.textContent)).toEqual([
      'Cancel',
      'Save',
    ]);
    fireEvent.click(within(form).getByRole('button', { name: 'Cancel' }));
    expect(screen.queryByRole('group')).toBeNull();
  });

  it('Edit opens the form with that item, and editing another starts its form afresh', () => {
    function Form({ initial }: { initial: Item | null }) {
      const [text, setText] = useState(initial?.name ?? '');
      return <input aria-label="name" value={text} onChange={(e) => setText(e.target.value)} />;
    }
    setup({ renderForm: (initial) => <Form initial={initial} /> });
    fireEvent.click(screen.getByRole('button', { name: 'Edit Beta' }));
    expect(screen.getByRole('group', { name: 'Edit thing' })).toBeTruthy();
    fireEvent.change(screen.getByLabelText('name'), { target: { value: 'typed' } });
    fireEvent.click(screen.getByRole('button', { name: 'Edit Alpha' }));
    expect((screen.getByLabelText('name') as HTMLInputElement).value).toBe('Alpha');
  });

  it('opening the form moves to its first field; closing it returns to the New button', async () => {
    setup({
      renderForm: (_initial, _onDone, footer) => (
        <form id={footer.formId}>
          <input aria-label="field" />
        </form>
      ),
    });
    fireEvent.click(screen.getByRole('button', { name: 'New thing' }));
    await waitFor(() => expect(document.activeElement).toBe(screen.getByLabelText('field')));
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    await waitFor(() =>
      expect(document.activeElement).toBe(screen.getByRole('button', { name: 'New thing' })),
    );
  });

  it('Save submits the form by id and is off while the form says it cannot be saved', () => {
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
    fireEvent.click(screen.getByRole('button', { name: 'New thing' }));
    const save = screen.getByRole('button', { name: 'Save' }) as HTMLButtonElement;
    expect(save.disabled).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: 'make valid' }));
    expect(save.disabled).toBe(false);
    fireEvent.click(save);
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });

  it('Delete confirms first, naming the item, and then calls onDelete with it', async () => {
    const props = setup();
    fireEvent.click(screen.getByRole('button', { name: 'Delete Alpha' }));
    expect(screen.getByText('"Alpha" will be removed. This cannot be undone.')).toBeTruthy();
    expect(props.onDelete).not.toHaveBeenCalled();
    confirmDelete();
    await waitFor(() => expect(props.onDelete).toHaveBeenCalledWith(items[0]));
  });

  it('cancelling delete keeps the item', () => {
    const props = setup();
    fireEvent.click(screen.getByRole('button', { name: 'Delete Alpha' }));
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(props.onDelete).not.toHaveBeenCalled();
    expect(screen.getByText('Alpha')).toBeTruthy();
  });

  it('deleting the item that is open in the form closes the form', async () => {
    setup();
    fireEvent.click(screen.getByRole('button', { name: 'Edit Alpha' }));
    fireEvent.click(screen.getByRole('button', { name: 'Delete Alpha' }));
    confirmDelete();
    await waitFor(() => expect(screen.queryByRole('group', { name: 'Edit thing' })).toBeNull());
  });

  it('a delete that fails says why', async () => {
    useToastStore.setState({ toasts: [] });
    const props = setup({
      onDelete: vi.fn(async () => {
        throw new Error('server 500');
      }),
    });
    fireEvent.click(screen.getByRole('button', { name: 'Delete Alpha' }));
    confirmDelete();
    await waitFor(() => expect(props.onDelete).toHaveBeenCalled());
    await waitFor(() =>
      expect(useToastStore.getState().toasts.some((t) => t.message === 'server 500')).toBe(true),
    );
  });
});
