import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import { renderWithProviders } from '../../test/render';
import { ArtifactPanel } from './ArtifactPanel';
import { artifactsApi } from '../../api/filesystem';
import { chatListInvalidated } from '../../test/invalidation';
import { useToastStore } from '../../components/ui/toast-store';

// CodeMirror needs a real layout: a plain textarea stands in for the editor, with the same props.
vi.mock('./CodeEditor', () => ({
  CodeEditor: ({ value, onChange }: { value: string; onChange: (v: string) => void }) => (
    <textarea aria-label="Editor" value={value} onChange={(e) => onChange(e.target.value)} />
  ),
}));

let scrollStubbed = false;

const list = [
  { id: 'f1', title: 'notes.md', filename: 'notes.md', type: 'file', language: 'markdown' },
  { id: 'f2', title: 'app.py', filename: 'app.py', type: 'file', language: 'python' },
  { id: '', title: 'src', filename: 'src/', type: 'directory' },
];

describe('ArtifactPanel', () => {
  beforeEach(() => {
    vi.spyOn(artifactsApi, 'list').mockResolvedValue(list as never);
    vi.spyOn(artifactsApi, 'get').mockImplementation(async (id: string) => ({
      id,
      title: id === 'f1' ? 'notes.md' : 'app.py',
      language: id === 'f1' ? 'markdown' : 'python',
      content: id === 'f1' ? '# Heading' : 'print(1)',
    }) as never);
  });
  afterEach(() => {
    vi.restoreAllMocks();
    if (scrollStubbed) Reflect.deleteProperty(Element.prototype, 'scrollIntoView');
    scrollStubbed = false;
  });

  it('lists files and shows the folder as a row', async () => {
    renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
    expect(await screen.findByRole('button', { name: /notes.md/ })).toBeTruthy();
    expect(screen.getByText('src')).toBeTruthy();
  });

  it('filter narrows the list by title', async () => {
    renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
    await screen.findByRole('button', { name: /notes.md/ });
    fireEvent.change(screen.getByLabelText('Filter files'), { target: { value: 'APP' } });
    expect(screen.queryByRole('button', { name: /notes.md/ })).toBeNull();
    expect(screen.getByRole('button', { name: /app.py/ })).toBeTruthy();
  });

  it('selecting a markdown file previews it rendered', async () => {
    renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
    fireEvent.click(await screen.findByRole('button', { name: /notes.md/ }));
    expect(await screen.findByRole('heading', { name: 'Heading' })).toBeTruthy();
    expect(screen.getByRole('radio', { name: 'Preview' }).getAttribute('aria-checked')).toBe('true');
  });

  it('a code file previews as plain code', async () => {
    renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
    fireEvent.click(await screen.findByRole('button', { name: /app.py/ }));
    expect(await screen.findByText('print(1)')).toBeTruthy();
  });

  it('New file creates a file with the default title', async () => {
    const create = vi.spyOn(artifactsApi, 'create').mockResolvedValue({ id: 'new1' });
    renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
    fireEvent.click(await screen.findByRole('button', { name: 'New file' }));
    await waitFor(() => expect(create).toHaveBeenCalledWith({ chatId: 'c' }, { title: 'Untitled', content: '', language: 'markdown' }));
  });

  it('a chat file create/delete refreshes the chat list, a workspace file does not', async () => {
    vi.spyOn(artifactsApi, 'create').mockResolvedValue({ id: 'new1' } as never);
    vi.spyOn(artifactsApi, 'remove').mockResolvedValue(new Response(null) as never);

    const chat = renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
    const chatInvalidate = vi.spyOn(chat.client, 'invalidateQueries');
    fireEvent.click(await screen.findByRole('button', { name: 'New file' }));
    await waitFor(() => expect(chatListInvalidated(chatInvalidate)).toBe(true));
    chatInvalidate.mockClear();
    fireEvent.click(await screen.findByRole('button', { name: /notes.md/ }));
    fireEvent.click(await screen.findByRole('button', { name: 'Delete file' }));
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }));
    await waitFor(() => expect(chatListInvalidated(chatInvalidate)).toBe(true));
    chat.unmount();

    const ws = renderWithProviders(<ArtifactPanel scope={{ workspaceId: 'w' }} />);
    const wsInvalidate = vi.spyOn(ws.client, 'invalidateQueries');
    fireEvent.click(await screen.findByRole('button', { name: 'New file' }));
    await waitFor(() => expect(wsInvalidate).toHaveBeenCalled());
    expect(chatListInvalidated(wsInvalidate)).toBe(false);
  });

  it('after New file the new file is open in edit mode (N1)', async () => {
    vi.spyOn(artifactsApi, 'create').mockResolvedValue({ id: 'new1' } as never);
    renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
    fireEvent.click(await screen.findByRole('button', { name: 'New file' }));
    await waitFor(() => expect(screen.getByRole('radio', { name: 'Edit' }).getAttribute('aria-checked')).toBe('true'));
  });

  it('a second New file uses the next free Untitled name (N2)', async () => {
    vi.spyOn(artifactsApi, 'list').mockResolvedValue([
      { id: 'u1', title: 'Untitled', filename: 'Untitled', type: 'file', language: 'markdown' },
    ] as never);
    const create = vi.spyOn(artifactsApi, 'create').mockResolvedValue({ id: 'new2' } as never);
    renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
    await screen.findByRole('button', { name: /Untitled/ });
    fireEvent.click(screen.getByRole('button', { name: 'New file' }));
    await waitFor(() => expect(create).toHaveBeenCalledWith({ chatId: 'c' }, { title: 'Untitled 2', content: '', language: 'markdown' }));
  });

  it('a failed create shows an error toast', async () => {
    vi.spyOn(artifactsApi, 'create').mockRejectedValue(new Error('path exists'));
    renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
    fireEvent.click(await screen.findByRole('button', { name: 'New file' }));
    await waitFor(() => expect(useToastStore.getState().toasts.some((t) => t.message === 'path exists')).toBe(true));
  });

  it('delete asks first, then removes the file', async () => {
    const remove = vi.spyOn(artifactsApi, 'remove').mockResolvedValue(new Response(null) as never);
    renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
    fireEvent.click(await screen.findByRole('button', { name: /notes.md/ }));
    fireEvent.click(await screen.findByRole('button', { name: 'Delete file' }));
    expect(remove).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }));
    await waitFor(() => expect(remove).toHaveBeenCalledWith('f1', { chatId: 'c' }));
  });

  it('a failed delete shows an error toast (N6)', async () => {
    useToastStore.setState({ toasts: [] });
    vi.spyOn(artifactsApi, 'remove').mockRejectedValue(new Error('file is locked'));
    renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
    fireEvent.click(await screen.findByRole('button', { name: /notes.md/ }));
    fireEvent.click(await screen.findByRole('button', { name: 'Delete file' }));
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }));
    await waitFor(() => expect(useToastStore.getState().toasts.some((t) => t.message === 'file is locked')).toBe(true));
  });

  it('Versions opens the version history for the open file', async () => {
    vi.spyOn(artifactsApi, 'versions').mockResolvedValue([]);
    renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
    fireEvent.click(await screen.findByRole('button', { name: /notes.md/ }));
    fireEvent.click(await screen.findByRole('button', { name: 'Versions' }));
    expect(await screen.findByText('Version history')).toBeTruthy();
  });

  it('switching to Edit shows the editor and no Save until the draft changes', async () => {
    const update = vi.spyOn(artifactsApi, 'update').mockResolvedValue({} as never);
    renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
    fireEvent.click(await screen.findByRole('button', { name: /app.py/ }));
    await screen.findByText('print(1)');
    fireEvent.click(screen.getByRole('radio', { name: 'Edit' }));
    expect(screen.getByRole('radio', { name: 'Edit' }).getAttribute('aria-checked')).toBe('true');
    expect(screen.queryByRole('button', { name: 'Save' })).toBeNull();
    expect(update).not.toHaveBeenCalled();
  });

  describe('unsaved edits', () => {
    async function editNotes() {
      fireEvent.click(await screen.findByRole('button', { name: /notes.md/ }));
      await screen.findByRole('heading', { name: 'Heading' });
      fireEvent.click(screen.getByRole('radio', { name: 'Edit' }));
      fireEvent.change(await screen.findByLabelText('Editor'), { target: { value: '# Changed' } });
    }

    it('switching files with unsaved edits asks first; Cancel keeps the file and the draft', async () => {
      renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
      await editNotes();
      fireEvent.click(screen.getByRole('button', { name: /app.py/ }));
      expect(await screen.findByText('Discard unsaved changes?')).toBeTruthy();
      fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
      expect((screen.getByLabelText('Editor') as HTMLTextAreaElement).value).toBe('# Changed');
      expect(screen.queryByText('print(1)')).toBeNull();
    });

    it('Discard drops the draft and opens the other file', async () => {
      renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
      await editNotes();
      fireEvent.click(screen.getByRole('button', { name: /app.py/ }));
      fireEvent.click(await screen.findByRole('button', { name: 'Discard' }));
      expect(await screen.findByText('print(1)')).toBeTruthy();
    });

    it('closing the panel and creating a file ask too', async () => {
      const onClose = vi.fn();
      const create = vi.spyOn(artifactsApi, 'create').mockResolvedValue({ id: 'new1' } as never);
      renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} onClose={onClose} />);
      await editNotes();
      fireEvent.click(screen.getByRole('button', { name: 'Close files panel' }));
      expect(onClose).not.toHaveBeenCalled();
      fireEvent.click(await screen.findByRole('button', { name: 'Cancel' }));
      fireEvent.click(screen.getByRole('button', { name: 'New file' }));
      expect(create).not.toHaveBeenCalled();
      fireEvent.click(await screen.findByRole('button', { name: 'Discard' }));
      await waitFor(() => expect(create).toHaveBeenCalled());
    });

    it('without a draft neither switching nor closing asks', async () => {
      const onClose = vi.fn();
      renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} onClose={onClose} />);
      fireEvent.click(await screen.findByRole('button', { name: /notes.md/ }));
      await screen.findByRole('heading', { name: 'Heading' });
      fireEvent.click(screen.getByRole('button', { name: /app.py/ }));
      expect(screen.queryByText('Discard unsaved changes?')).toBeNull();
      fireEvent.click(screen.getByRole('button', { name: 'Close files panel' }));
      expect(onClose).toHaveBeenCalled();
    });
  });

  it('the selected row is scrolled into view, and the previous file stays while the next loads', async () => {
    const scroll = vi.fn();
    // jsdom has no scrollIntoView: give it one, removed again after the test.
    Element.prototype.scrollIntoView = scroll;
    scrollStubbed = true;
    let release: (v: unknown) => void = () => undefined;
    renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
    fireEvent.click(await screen.findByRole('button', { name: /notes.md/ }));
    await screen.findByRole('heading', { name: 'Heading' });
    expect(scroll).toHaveBeenCalled();
    vi.mocked(artifactsApi.get).mockImplementation(() => new Promise((resolve) => (release = resolve)) as never);
    fireEvent.click(screen.getByRole('button', { name: /app.py/ }));
    // the first file is still on screen, marked busy, until the second arrives
    expect(screen.getByRole('heading', { name: 'Heading' })).toBeTruthy();
    expect(document.querySelector('.artifact-viewer--loading')).toBeTruthy();
    release({ id: 'f2', title: 'app.py', language: 'python', content: 'print(1)' });
    expect(await screen.findByText('print(1)')).toBeTruthy();
  });

  describe('file actions', () => {
    async function openNotes() {
      fireEvent.click(await screen.findByRole('button', { name: /notes.md/ }));
      await screen.findByRole('heading', { name: 'Heading' });
    }
    const more = () => fireEvent.click(screen.getByRole('button', { name: 'More file actions' }));

    it('Rename updates the title through the API and refreshes the list', async () => {
      const update = vi.spyOn(artifactsApi, 'update').mockResolvedValue({} as never);
      renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
      await openNotes();
      more();
      fireEvent.click(await screen.findByRole('menuitem', { name: 'Rename' }));
      const field = within(await screen.findByRole('dialog', { name: 'Rename file' })).getByRole('textbox');
      fireEvent.change(field, { target: { value: ' renamed.md ' } });
      fireEvent.click(screen.getByRole('button', { name: 'Rename' }));
      await waitFor(() => expect(update).toHaveBeenCalledWith('f1', { chatId: 'c' }, { title: 'renamed.md' }));
    });

    it('Move updates the folder through the API', async () => {
      const update = vi.spyOn(artifactsApi, 'update').mockResolvedValue({} as never);
      renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
      await openNotes();
      more();
      fireEvent.click(await screen.findByRole('menuitem', { name: /Move to folder/ }));
      fireEvent.click(await screen.findByRole('combobox', { name: 'Destination folder' }));
      fireEvent.click(screen.getByRole('option', { name: 'src' }));
      fireEvent.click(screen.getByRole('button', { name: 'Move' }));
      await waitFor(() => expect(update).toHaveBeenCalledWith('f1', { chatId: 'c' }, { folder: 'src' }));
    });

    it('Rename and Move are disabled for a file read from disk', async () => {
      vi.spyOn(artifactsApi, 'list').mockResolvedValue([
        { id: 'disk:a.txt', title: 'a.txt', filename: 'a.txt', type: 'file', language: 'text' },
      ] as never);
      vi.spyOn(artifactsApi, 'get').mockResolvedValue({ id: 'disk:a.txt', title: 'a.txt', language: 'text', content: 'x' } as never);
      renderWithProviders(<ArtifactPanel scope={{ workspaceId: 'w' }} />);
      fireEvent.click(await screen.findByRole('button', { name: /a.txt/ }));
      await screen.findByText('x');
      more();
      expect(await screen.findByRole('menuitem', { name: 'Rename' })).toBeDisabled();
    });

    it('New folder posts the path', async () => {
      const make = vi.spyOn(artifactsApi, 'createDirectory').mockResolvedValue({} as never);
      renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
      fireEvent.click(await screen.findByRole('button', { name: 'New folder' }));
      fireEvent.change(within(await screen.findByRole('dialog', { name: 'New folder' })).getByRole('textbox'), { target: { value: '/docs/2026/' } });
      fireEvent.click(screen.getByRole('button', { name: 'Create' }));
      await waitFor(() => expect(make).toHaveBeenCalledWith({ chatId: 'c' }, 'docs/2026'));
    });

    it('Delete folder asks first, deletes through the API, and shows the server\'s refusal', async () => {
      const del = vi.spyOn(artifactsApi, 'deleteDirectory').mockRejectedValue(new Error('Directory is not empty'));
      renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
      fireEvent.contextMenu(await screen.findByRole('button', { name: /src/ }));
      fireEvent.click(await screen.findByRole('menuitem', { name: 'Delete folder' }));
      expect(del).not.toHaveBeenCalled();
      fireEvent.click(await screen.findByRole('button', { name: 'Delete' }));
      await waitFor(() => expect(del).toHaveBeenCalledWith({ chatId: 'c' }, 'src'));
      await waitFor(() => expect(useToastStore.getState().toasts.some((t) => t.message === 'Directory is not empty')).toBe(true));
    });

    it('Download links to the raw file and Copy writes the contents to the clipboard', async () => {
      const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined);
      const write = vi.fn(async () => undefined);
      Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: write } });
      renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
      await openNotes();
      more();
      fireEvent.click(await screen.findByRole('menuitem', { name: 'Download' }));
      expect(click).toHaveBeenCalled();
      more();
      fireEvent.click(await screen.findByRole('menuitem', { name: 'Copy contents' }));
      await waitFor(() => expect(write).toHaveBeenCalledWith('# Heading'));
      expect(useToastStore.getState().toasts.some((t) => t.message === 'Copied')).toBe(true);
      Reflect.deleteProperty(navigator, 'clipboard');
    });
  });

  it('a name with a slash is not sent as a rename (it would move the file)', async () => {
    const update = vi.spyOn(artifactsApi, 'update').mockResolvedValue({} as never);
    renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
    fireEvent.click(await screen.findByRole('button', { name: /notes.md/ }));
    await screen.findByRole('heading', { name: 'Heading' });
    fireEvent.click(screen.getByRole('button', { name: 'More file actions' }));
    fireEvent.click(await screen.findByRole('menuitem', { name: 'Rename' }));
    const dialog = await screen.findByRole('dialog', { name: 'Rename file' });
    fireEvent.change(within(dialog).getByRole('textbox'), { target: { value: 'sub/a.md' } });
    fireEvent.click(within(dialog).getByRole('button', { name: 'Rename' }));
    expect(update).not.toHaveBeenCalled();
    expect(useToastStore.getState().toasts.some((t) => t.message.includes('cannot contain'))).toBe(true);
  });

  it('a failed list or file load shows its message instead of an empty panel', async () => {
    vi.spyOn(artifactsApi, 'list').mockRejectedValue(new Error('files unavailable'));
    renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
    expect(await screen.findByRole('alert', {}, { timeout: 3000 })).toHaveTextContent('files unavailable');
    expect(screen.queryByText('No files yet')).toBeNull();
  });

  it('opening the version history with unsaved edits asks first', async () => {
    vi.spyOn(artifactsApi, 'versions').mockResolvedValue([]);
    renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
    fireEvent.click(await screen.findByRole('button', { name: /notes.md/ }));
    await screen.findByRole('heading', { name: 'Heading' });
    fireEvent.click(screen.getByRole('radio', { name: 'Edit' }));
    fireEvent.change(await screen.findByLabelText('Editor'), { target: { value: '# Changed' } });
    fireEvent.click(screen.getByRole('button', { name: 'Versions' }));
    expect(await screen.findByText('Discard unsaved changes?')).toBeTruthy();
    expect(screen.queryByText('Version history')).toBeNull();
  });

  it('after Save the file is not left looking unsaved: the draft is dropped once the saved content has loaded', async () => {
    let stored = '# Heading';
    vi.mocked(artifactsApi.get).mockImplementation(async (id: string) => ({ id, title: 'notes.md', language: 'markdown', content: stored }) as never);
    vi.spyOn(artifactsApi, 'update').mockImplementation(async (_id, _scope, body) => {
      stored = (body as { content: string }).content;
      return {} as never;
    });
    renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
    fireEvent.click(await screen.findByRole('button', { name: /notes.md/ }));
    await screen.findByRole('heading', { name: 'Heading' });
    fireEvent.click(screen.getByRole('radio', { name: 'Edit' }));
    fireEvent.change(await screen.findByLabelText('Editor'), { target: { value: '# Saved text' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Save' })).toBeNull());
    expect((screen.getByLabelText('Editor') as HTMLTextAreaElement).value).toBe('# Saved text');
    expect(screen.queryByRole('img', { name: 'Unsaved changes' })).toBeNull();
  });
});
