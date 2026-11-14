import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import { artifactsApi, artifactsKey, codeExecApi } from '../../api/filesystem';
import { clarificationApi } from '../../api/tools';
import { useToastStore } from '../../components/ui/toast-store';
import { useStreamStore } from '../../state/stream-store';
import { useUiStore } from '../../state/ui-store';
import { chatListInvalidated } from '../../test/invalidation';
import { renderWithProviders } from '../../test/render';
import { emptyLiveTurn } from '../chat/stream-reducer';
import { ArtifactPanel } from './ArtifactPanel';

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
  {
    id: 'f4',
    title: 'util.py',
    filename: 'util.py',
    folder: 'src',
    type: 'file',
    language: 'python',
  },
];
const CONTENT: Record<string, string> = {
  f1: '# Heading',
  f2: 'print(1)',
  f4: 'def helper():\n    return 42',
};

const toasts = () => useToastStore.getState().toasts.map((t) => t.message);
const file = (name: RegExp) => screen.findByRole('button', { name });
const editorText = () => (screen.getByLabelText('Editor') as HTMLTextAreaElement).value;

async function openNotes() {
  fireEvent.click(await file(/^notes.md/));
  await screen.findByRole('heading', { name: 'Heading' });
}
async function openApp() {
  fireEvent.click(await file(/^app.py/));
  await waitFor(() => expect(editorText()).toBe('print(1)'));
}
async function typeInNotes(text: string) {
  await openNotes();
  fireEvent.click(screen.getByRole('radio', { name: 'Code' }));
  fireEvent.change(await screen.findByLabelText('Editor'), { target: { value: text } });
}
/** Opens the + menu and picks an entry. */
async function newThing(entry: 'New file' | 'New folder') {
  fireEvent.click(await screen.findByRole('button', { name: 'New file or folder' }));
  fireEvent.click(await screen.findByRole('menuitem', { name: entry }));
  return screen.findByRole('dialog', { name: entry });
}
async function moreFor(entry: string | RegExp) {
  fireEvent.click(screen.getByRole('button', { name: 'More' }));
  fireEvent.click(await screen.findByRole('menuitem', { name: entry }));
}

describe('ArtifactPanel', () => {
  beforeEach(() => {
    useToastStore.setState({ toasts: [] });
    CONTENT.f1 = '# Heading';
    vi.spyOn(artifactsApi, 'list').mockResolvedValue(list as never);
    vi.spyOn(artifactsApi, 'currentVersion').mockResolvedValue(3);
    vi.spyOn(artifactsApi, 'get').mockImplementation(async (id: string) => {
      const entry = list.find((a) => a.id === id);
      return {
        id,
        title: entry?.title,
        language: entry?.language,
        content: CONTENT[id] ?? '',
      } as never;
    });
  });
  afterEach(() => {
    vi.restoreAllMocks();
    useStreamStore.setState({ chatId: null, live: null });
    if (scrollStubbed) Reflect.deleteProperty(Element.prototype, 'scrollIntoView');
    scrollStubbed = false;
  });

  describe('the list', () => {
    it('shows files and folders nested, with how many files a folder holds', async () => {
      renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
      expect(await file(/^notes.md/)).toBeTruthy();
      const folder = screen.getByRole('button', { name: /^src/ });
      expect(folder).toHaveTextContent('1');
      expect(folder.getAttribute('aria-expanded')).toBe('true');
      expect(screen.getByRole('button', { name: /^util.py/ })).toBeTruthy();
      fireEvent.click(folder);
      expect(screen.queryByRole('button', { name: /^util.py/ })).toBeNull();
    });

    it('search narrows the list by name', async () => {
      renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
      await file(/^notes.md/);
      fireEvent.change(screen.getByLabelText('Search files'), { target: { value: 'APP' } });
      expect(screen.queryByRole('button', { name: /notes.md/ })).toBeNull();
      expect(screen.getByRole('button', { name: /app.py/ })).toBeTruthy();
      // Each file says what kind it is at the end of its row.
      expect(screen.getByRole('button', { name: /app.py/ }).textContent).toMatch(/py$/);
    });

    it('search finds words inside a file that has been opened and shows the line', async () => {
      renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
      fireEvent.click(await file(/^util.py/));
      await waitFor(() => expect(editorText()).toContain('helper'));
      fireEvent.change(screen.getByLabelText('Search files'), { target: { value: 'return 42' } });
      const results = screen.getByRole('list', { name: 'Search results' });
      expect(within(results).getByText('src/util.py')).toBeTruthy();
      expect(within(results).getByText('Line 2')).toBeTruthy();
    });

    it('says so when nothing matches, and what is searched', async () => {
      renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
      await file(/^notes.md/);
      fireEvent.change(screen.getByLabelText('Search files'), { target: { value: 'zzz' } });
      expect(screen.getByText('Nothing matches')).toBeTruthy();
    });

    it('a failed list shows its message instead of an empty panel', async () => {
      vi.spyOn(artifactsApi, 'list').mockRejectedValue(new Error('files unavailable'));
      renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
      expect(await screen.findByRole('alert', {}, { timeout: 3000 })).toHaveTextContent(
        'files unavailable',
      );
      expect(screen.queryByText('No files yet')).toBeNull();
    });
  });

  describe('opening a file', () => {
    it('a markdown file opens rendered, with Code / Preview and its labels', async () => {
      renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
      await openNotes();
      expect(screen.getByRole('radio', { name: 'Preview' }).getAttribute('aria-checked')).toBe(
        'true',
      );
      expect(screen.getByText('Markdown')).toBeTruthy();
      expect(await screen.findByText('v3')).toBeTruthy();
      expect(screen.getByText('Saved')).toBeTruthy();
    });

    it('a code file opens in the editor and has no preview', async () => {
      renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
      await openApp();
      expect(screen.queryByRole('radio', { name: 'Preview' })).toBeNull();
    });

    it('selects the file a transcript link asked for once the list is in', async () => {
      useUiStore.setState({ requestedArtifactPath: './app.py' });
      renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
      await waitFor(() => expect(editorText()).toBe('print(1)'));
      expect(useUiStore.getState().requestedArtifactPath).toBeNull();
    });

    it('waits for the refetch before it says a file is missing (the panel opens on a stale cached list)', async () => {
      const fresh = [
        ...list,
        { id: 'f3', title: 'new.md', filename: 'new.md', type: 'file', language: 'markdown' },
      ];
      vi.spyOn(artifactsApi, 'list').mockResolvedValue(fresh as never);
      vi.spyOn(artifactsApi, 'get').mockResolvedValue({
        id: 'f3',
        title: 'new.md',
        language: 'markdown',
        content: '# New file',
      } as never);
      const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
      client.setQueryData(artifactsKey({ chatId: 'c' }), list); // cached before the agent wrote new.md
      useUiStore.setState({ requestedArtifactPath: 'new.md' });
      render(
        <QueryClientProvider client={client}>
          <MemoryRouter>
            <ArtifactPanel scope={{ chatId: 'c' }} />
          </MemoryRouter>
        </QueryClientProvider>,
      );
      expect(await screen.findByRole('heading', { name: 'New file' })).toBeTruthy();
      expect(toasts().some((m) => m.startsWith('File not found'))).toBe(false);
    });

    it('clears a pending request and says so when the file list cannot be loaded', async () => {
      vi.spyOn(artifactsApi, 'list').mockRejectedValue(new Error('offline'));
      useUiStore.setState({ requestedArtifactPath: 'notes.md' });
      renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
      await waitFor(() => expect(useUiStore.getState().requestedArtifactPath).toBeNull());
      expect(toasts()).toContain("Couldn't load the files");
    });

    it('says once that a requested file is not in the list', async () => {
      useUiStore.setState({ requestedArtifactPath: 'missing.md' });
      renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
      await waitFor(() => expect(useUiStore.getState().requestedArtifactPath).toBeNull());
      expect(toasts().filter((m) => m === 'File not found: missing.md')).toHaveLength(1);
    });

    it('the selected row is scrolled into view, and the previous file stays while the next loads', async () => {
      const scroll = vi.fn();
      // jsdom has no scrollIntoView: give it one, removed again after the test.
      Element.prototype.scrollIntoView = scroll;
      scrollStubbed = true;
      let release: (v: unknown) => void = () => undefined;
      renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
      await openNotes();
      expect(scroll).toHaveBeenCalled();
      vi.mocked(artifactsApi.get).mockImplementation(
        () => new Promise((resolve) => (release = resolve)) as never,
      );
      fireEvent.click(screen.getByRole('button', { name: /^app.py/ }));
      // the first file is still on screen, marked busy, until the second arrives
      await waitFor(() =>
        expect(document.querySelector('.fb-edit[aria-busy="true"]')).toBeTruthy(),
      );
      expect(screen.getByRole('heading', { name: 'Heading' })).toBeTruthy();
      release({ id: 'f2', title: 'app.py', language: 'python', content: 'print(1)' });
      await waitFor(() => expect(editorText()).toBe('print(1)'));
    });

    it('a file that cannot be opened shows its message', async () => {
      vi.mocked(artifactsApi.get).mockRejectedValue(new Error('file is gone'));
      renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
      fireEvent.click(await file(/^notes.md/));
      expect(await screen.findByRole('alert', {}, { timeout: 3000 })).toHaveTextContent(
        'file is gone',
      );
    });
  });

  describe('new files and folders', () => {
    it('New file asks where and what name, then creates it', async () => {
      const create = vi.spyOn(artifactsApi, 'create').mockResolvedValue({ id: 'new1' });
      renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
      await file(/^notes.md/);
      const popup = await newThing('New file');
      expect((within(popup).getByLabelText('File name') as HTMLInputElement).value).toBe(
        'Untitled',
      );
      fireEvent.click(within(popup).getByRole('button', { name: 'Create file' }));
      await waitFor(() =>
        expect(create).toHaveBeenCalledWith(
          { chatId: 'c' },
          { title: 'Untitled', content: '', language: 'markdown' },
        ),
      );
    });

    it('the name gives the language and Where gives the folder', async () => {
      const create = vi.spyOn(artifactsApi, 'create').mockResolvedValue({ id: 'new1' });
      renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
      await file(/^notes.md/);
      const popup = await newThing('New file');
      fireEvent.change(within(popup).getByLabelText('File name'), {
        target: { value: ' run.py ' },
      });
      fireEvent.click(within(popup).getByRole('combobox', { name: 'Where' }));
      fireEvent.click(screen.getByRole('option', { name: 'src' }));
      fireEvent.click(within(popup).getByRole('button', { name: 'Create file' }));
      await waitFor(() =>
        expect(create).toHaveBeenCalledWith(
          { chatId: 'c' },
          { title: 'run.py', content: '', language: 'python', folder: 'src' },
        ),
      );
    });

    it('a second new file is offered the next free Untitled name', async () => {
      vi.spyOn(artifactsApi, 'list').mockResolvedValue([
        { id: 'u1', title: 'Untitled', filename: 'Untitled', type: 'file', language: 'markdown' },
      ] as never);
      renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
      await file(/^Untitled/);
      const popup = await newThing('New file');
      expect((within(popup).getByLabelText('File name') as HTMLInputElement).value).toBe(
        'Untitled 2',
      );
    });

    it('the new file is open in the editor', async () => {
      vi.spyOn(artifactsApi, 'create').mockResolvedValue({ id: 'f1' } as never);
      renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
      await file(/^notes.md/);
      fireEvent.click(
        within(await newThing('New file')).getByRole('button', { name: 'Create file' }),
      );
      await waitFor(() =>
        expect(screen.getByRole('radio', { name: 'Code' }).getAttribute('aria-checked')).toBe(
          'true',
        ),
      );
      expect(screen.getByLabelText('Editor')).toBeTruthy();
    });

    it('a name is needed, and a slash is refused where it is typed', async () => {
      const create = vi.spyOn(artifactsApi, 'create').mockResolvedValue({ id: 'new1' });
      renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
      await file(/^notes.md/);
      const popup = await newThing('New file');
      fireEvent.change(within(popup).getByLabelText('File name'), {
        target: { value: 'sub/a.md' },
      });
      fireEvent.click(within(popup).getByRole('button', { name: 'Create file' }));
      expect(within(popup).getByText(/cannot contain/)).toBeTruthy();
      fireEvent.change(within(popup).getByLabelText('File name'), { target: { value: '  ' } });
      fireEvent.click(within(popup).getByRole('button', { name: 'Create file' }));
      expect(within(popup).getByText('Give it a name.')).toBeTruthy();
      expect(create).not.toHaveBeenCalled();
    });

    it('a failed create shows the reason', async () => {
      vi.spyOn(artifactsApi, 'create').mockRejectedValue(new Error('path exists'));
      renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
      await file(/^notes.md/);
      fireEvent.click(
        within(await newThing('New file')).getByRole('button', { name: 'Create file' }),
      );
      await waitFor(() => expect(toasts()).toContain('path exists'));
    });

    it('a chat file create or delete refreshes the chat list, a workspace file does not', async () => {
      vi.spyOn(artifactsApi, 'create').mockResolvedValue({ id: 'new1' } as never);
      vi.spyOn(artifactsApi, 'remove').mockResolvedValue(new Response(null) as never);

      const chat = renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
      const chatInvalidate = vi.spyOn(chat.client, 'invalidateQueries');
      await file(/^notes.md/);
      fireEvent.click(
        within(await newThing('New file')).getByRole('button', { name: 'Create file' }),
      );
      await waitFor(() => expect(chatListInvalidated(chatInvalidate)).toBe(true));
      chatInvalidate.mockClear();
      await openNotes();
      await moreFor('Delete');
      fireEvent.click(await screen.findByRole('button', { name: 'Delete file' }));
      await waitFor(() => expect(chatListInvalidated(chatInvalidate)).toBe(true));
      chat.unmount();

      const ws = renderWithProviders(<ArtifactPanel scope={{ workspaceId: 'w' }} />);
      const wsInvalidate = vi.spyOn(ws.client, 'invalidateQueries');
      await file(/^notes.md/);
      fireEvent.click(
        within(await newThing('New file')).getByRole('button', { name: 'Create file' }),
      );
      await waitFor(() => expect(wsInvalidate).toHaveBeenCalled());
      expect(chatListInvalidated(wsInvalidate)).toBe(false);
    });

    it('New folder is made at the top level or inside the chosen folder', async () => {
      const make = vi.spyOn(artifactsApi, 'createDirectory').mockResolvedValue({} as never);
      renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
      await file(/^notes.md/);
      let popup = await newThing('New folder');
      fireEvent.change(within(popup).getByLabelText('Folder name'), { target: { value: 'docs' } });
      fireEvent.click(within(popup).getByRole('button', { name: 'Create folder' }));
      await waitFor(() => expect(make).toHaveBeenCalledWith({ chatId: 'c' }, 'docs'));

      fireEvent.contextMenu(screen.getByRole('button', { name: /^src/ }));
      fireEvent.click(await screen.findByRole('menuitem', { name: 'New folder here' }));
      popup = await screen.findByRole('dialog', { name: 'New folder' });
      fireEvent.change(within(popup).getByLabelText('Folder name'), { target: { value: 'lib' } });
      fireEvent.click(within(popup).getByRole('button', { name: 'Create folder' }));
      await waitFor(() => expect(make).toHaveBeenCalledWith({ chatId: 'c' }, 'src/lib'));
    });

    it("Delete folder asks first, deletes through the API, and shows the server's refusal", async () => {
      const del = vi
        .spyOn(artifactsApi, 'deleteDirectory')
        .mockRejectedValue(new Error('Directory is not empty'));
      renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
      fireEvent.click(await screen.findByRole('button', { name: 'More for src' }));
      fireEvent.click(await screen.findByRole('menuitem', { name: 'Delete folder' }));
      expect(del).not.toHaveBeenCalled();
      fireEvent.click(await screen.findByRole('button', { name: 'Delete folder' }));
      await waitFor(() => expect(del).toHaveBeenCalledWith({ chatId: 'c' }, 'src'));
      await waitFor(() => expect(toasts()).toContain('Directory is not empty'));
    });
  });

  describe('saving by itself', () => {
    it('there is no Save button: an edit is saved after a pause and the light says so', async () => {
      const update = vi.spyOn(artifactsApi, 'update').mockResolvedValue({} as never);
      renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
      await typeInNotes('# Changed');
      expect(screen.queryByRole('button', { name: 'Save' })).toBeNull();
      expect(screen.getByText('Saving')).toBeTruthy();
      expect(update).not.toHaveBeenCalled();
      await waitFor(
        () => expect(update).toHaveBeenCalledWith('f1', { chatId: 'c' }, { content: '# Changed' }),
        {
          timeout: 3000,
        },
      );
      expect(await screen.findByText('Saved')).toBeTruthy();
      expect(editorText()).toBe('# Changed');
    });

    it('once saved, a change made elsewhere to the same file is shown, not hidden by the typed text', async () => {
      vi.spyOn(artifactsApi, 'update').mockResolvedValue({} as never);
      const { client } = renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
      await typeInNotes('# Changed');
      expect(await screen.findByText('Saved', {}, { timeout: 3000 })).toBeTruthy();
      act(() => {
        client.setQueryData(
          ['artifact', 'f1', artifactsKey({ chatId: 'c' })[1]],
          (old: object | undefined) => (old ? { ...old, content: '# From the model' } : old),
        );
      });
      await waitFor(() => expect(editorText()).toBe('# From the model'));
    });

    it('opening a file changes nothing, so nothing is saved', async () => {
      const update = vi.spyOn(artifactsApi, 'update').mockResolvedValue({} as never);
      renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
      await openApp();
      fireEvent.change(screen.getByLabelText('Editor'), { target: { value: 'print(1)' } });
      fireEvent.click(screen.getByRole('button', { name: /^notes.md/ }));
      await screen.findByRole('heading', { name: 'Heading' });
      expect(update).not.toHaveBeenCalled();
    });

    it('switching files saves the unsaved text first, without asking', async () => {
      const update = vi.spyOn(artifactsApi, 'update').mockResolvedValue({} as never);
      renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
      await typeInNotes('# Changed');
      fireEvent.click(screen.getByRole('button', { name: /^app.py/ }));
      await waitFor(() => expect(editorText()).toBe('print(1)'));
      expect(update).toHaveBeenCalledWith('f1', { chatId: 'c' }, { content: '# Changed' });
      expect(screen.queryByRole('dialog')).toBeNull();
      // and the saved text is what the first file shows on the way back
      fireEvent.click(screen.getByRole('button', { name: /^notes.md/ }));
      await waitFor(() => expect(editorText()).toBe('# Changed'));
    });

    it('when a save fails the file stays open with its text, and can be tried again', async () => {
      const update = vi.spyOn(artifactsApi, 'update').mockRejectedValue(new Error('disk full'));
      renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
      await typeInNotes('# Changed');
      fireEvent.click(screen.getByRole('button', { name: /^app.py/ }));
      expect(await screen.findByText(/could not be saved/)).toBeTruthy();
      expect(editorText()).toBe('# Changed');
      expect(toasts()).toContain("Couldn't save your changes, so this file stays open");
      expect(screen.getByText('Not saved')).toBeTruthy();
      update.mockResolvedValue({} as never);
      fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
      expect(await screen.findByText('Saved')).toBeTruthy();
    });

    it('closing the panel saves first; it stays open when that fails', async () => {
      const onClose = vi.fn();
      const update = vi.spyOn(artifactsApi, 'update').mockRejectedValue(new Error('offline'));
      renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} onClose={onClose} />);
      await typeInNotes('# Changed');
      fireEvent.click(screen.getByRole('button', { name: 'Close files' }));
      await waitFor(() => expect(update).toHaveBeenCalled());
      await screen.findByText('Not saved');
      expect(onClose).not.toHaveBeenCalled();
      update.mockResolvedValue({} as never);
      fireEvent.click(screen.getByRole('button', { name: 'Close files' }));
      await waitFor(() => expect(onClose).toHaveBeenCalled());
      expect(update).toHaveBeenLastCalledWith('f1', { chatId: 'c' }, { content: '# Changed' });
    });

    it('a panel that goes away saves what was still unsaved', async () => {
      const update = vi.spyOn(artifactsApi, 'update').mockResolvedValue({} as never);
      const view = renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
      await typeInNotes('# Changed');
      view.unmount();
      await waitFor(() =>
        expect(update).toHaveBeenCalledWith('f1', { chatId: 'c' }, { content: '# Changed' }),
      );
    });

    it('a tick box in the preview ticks the box in the file and saves it', async () => {
      CONTENT.f1 = '- [ ] first\n- [ ] second';
      const update = vi.spyOn(artifactsApi, 'update').mockResolvedValue({} as never);
      const view = renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
      fireEvent.click(await file(/^notes.md/));
      await screen.findByText('second');
      const boxes = screen.getAllByRole('checkbox');
      expect(boxes[1]).not.toBeDisabled();
      // The whole line is the target: pressing its words ticks the box.
      fireEvent.click(screen.getByText('second'));
      view.unmount();
      await waitFor(() =>
        expect(update).toHaveBeenCalledWith(
          'f1',
          { chatId: 'c' },
          { content: '- [ ] first\n- [x] second' },
        ),
      );
    });
  });

  describe('file actions', () => {
    it('delete asks first, then removes the file', async () => {
      const remove = vi
        .spyOn(artifactsApi, 'remove')
        .mockResolvedValue(new Response(null) as never);
      renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
      await openNotes();
      await moreFor('Delete');
      expect(remove).not.toHaveBeenCalled();
      fireEvent.click(await screen.findByRole('button', { name: 'Delete file' }));
      await waitFor(() => expect(remove).toHaveBeenCalledWith('f1', { chatId: 'c' }));
    });

    it('a failed delete shows the reason', async () => {
      vi.spyOn(artifactsApi, 'remove').mockRejectedValue(new Error('file is locked'));
      renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
      await openNotes();
      await moreFor('Delete');
      fireEvent.click(await screen.findByRole('button', { name: 'Delete file' }));
      await waitFor(() => expect(toasts()).toContain('file is locked'));
    });

    it('a row has its own menu, from its More button or a right-click', async () => {
      const remove = vi
        .spyOn(artifactsApi, 'remove')
        .mockResolvedValue(new Response(null) as never);
      renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
      fireEvent.contextMenu(await file(/^app.py/));
      const menu = await screen.findByRole('menu');
      expect(
        within(menu)
          .getAllByRole('menuitem')
          .map((i) => i.textContent),
      ).toEqual(['Open', 'Run', 'Download', 'Rename or move…', 'Delete']);
      fireEvent.click(within(menu).getByRole('menuitem', { name: 'Delete' }));
      fireEvent.click(await screen.findByRole('button', { name: 'Delete file' }));
      await waitFor(() => expect(remove).toHaveBeenCalledWith('f2', { chatId: 'c' }));
    });

    it('Version history opens for the open file', async () => {
      vi.spyOn(artifactsApi, 'versions').mockResolvedValue([]);
      renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
      await openNotes();
      fireEvent.click(screen.getByRole('button', { name: 'Version history' }));
      expect(await screen.findByRole('dialog')).toHaveTextContent('Version history');
    });

    it('Rename or move changes the name, the folder, or both, and nothing when nothing changed', async () => {
      const update = vi.spyOn(artifactsApi, 'update').mockResolvedValue({} as never);
      renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
      await openNotes();
      await moreFor('Rename or move…');
      let popup = await screen.findByRole('dialog', { name: 'Rename or move' });
      fireEvent.click(within(popup).getByRole('button', { name: 'Save' }));
      expect(update).not.toHaveBeenCalled();

      await moreFor('Rename or move…');
      popup = await screen.findByRole('dialog', { name: 'Rename or move' });
      fireEvent.change(within(popup).getByLabelText('File name'), {
        target: { value: ' renamed.md ' },
      });
      fireEvent.click(within(popup).getByRole('button', { name: 'Save' }));
      await waitFor(() =>
        expect(update).toHaveBeenCalledWith('f1', { chatId: 'c' }, { title: 'renamed.md' }),
      );

      await moreFor('Rename or move…');
      popup = await screen.findByRole('dialog', { name: 'Rename or move' });
      fireEvent.click(within(popup).getByRole('combobox', { name: 'Where' }));
      fireEvent.click(screen.getByRole('option', { name: 'src' }));
      fireEvent.click(within(popup).getByRole('button', { name: 'Save' }));
      await waitFor(() =>
        expect(update).toHaveBeenCalledWith('f1', { chatId: 'c' }, { folder: 'src' }),
      );
    });

    it('a file read from disk cannot be renamed or moved', async () => {
      vi.spyOn(artifactsApi, 'list').mockResolvedValue([
        { id: 'disk:a.txt', title: 'a.txt', filename: 'a.txt', type: 'file', language: 'text' },
      ] as never);
      vi.spyOn(artifactsApi, 'get').mockResolvedValue({
        id: 'disk:a.txt',
        title: 'a.txt',
        language: 'text',
        content: 'x',
      } as never);
      renderWithProviders(<ArtifactPanel scope={{ workspaceId: 'w' }} />);
      fireEvent.click(await file(/^a.txt/));
      await waitFor(() => expect(editorText()).toBe('x'));
      fireEvent.click(screen.getByRole('button', { name: 'More' }));
      expect(await screen.findByRole('menuitem', { name: /Rename or move/ })).toBeDisabled();
    });

    it('Download links to the raw file and Copy writes the contents to the clipboard', async () => {
      const click = vi
        .spyOn(HTMLAnchorElement.prototype, 'click')
        .mockImplementation(() => undefined);
      const write = vi.fn(async () => undefined);
      Object.defineProperty(navigator, 'clipboard', {
        configurable: true,
        value: { writeText: write },
      });
      renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
      await openNotes();
      await moreFor('Download');
      expect(click).toHaveBeenCalled();
      fireEvent.click(screen.getByRole('button', { name: 'Copy' }));
      await waitFor(() => expect(write).toHaveBeenCalledWith('# Heading'));
      expect(toasts()).toContain('Copied');
      Reflect.deleteProperty(navigator, 'clipboard');
    });

    it('Run saves, runs the file and shows what it printed', async () => {
      const runFile = vi.spyOn(codeExecApi, 'runFile').mockResolvedValue('1\n');
      renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
      await openApp();
      fireEvent.click(screen.getByRole('button', { name: 'Run' }));
      const output = await screen.findByRole('region', { name: 'Run output' });
      await waitFor(() => expect(within(output).getByText('Finished')).toBeTruthy());
      expect(runFile).toHaveBeenCalledWith('c', 'app.py');
      expect(output).toHaveTextContent('1');
      fireEvent.click(within(output).getByRole('button', { name: 'Close the output' }));
      expect(screen.queryByRole('region', { name: 'Run output' })).toBeNull();
    });

    it('a run that fails says why; a file that cannot be run has Run switched off', async () => {
      vi.spyOn(codeExecApi, 'runFile').mockRejectedValue(new Error('Could not run the file. Try again.'));
      renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
      await openApp();
      fireEvent.click(screen.getByRole('button', { name: 'Run' }));
      const output = await screen.findByRole('region', { name: 'Run output' });
      await waitFor(() => expect(within(output).getByText('Did not run')).toBeTruthy());
      expect(output).toHaveTextContent('Could not run the file. Try again.');
      fireEvent.click(screen.getByRole('button', { name: /^notes.md/ }));
      await screen.findByRole('heading', { name: 'Heading' });
      expect(screen.getByRole('button', { name: 'Run' })).toBeDisabled();
    });

    it('in a workspace Run and Version history are off and say why', async () => {
      renderWithProviders(<ArtifactPanel scope={{ workspaceId: 'w' }} />);
      await openApp();
      expect(screen.getByRole('button', { name: 'Run' })).toHaveAttribute(
        'aria-description',
        expect.stringContaining('chat'),
      );
      expect(screen.getByRole('button', { name: 'Version history' })).toBeDisabled();
    });
  });

  describe('full screen', () => {
    it('lifts the same browser out and puts it back: the file and what was typed are still there', async () => {
      vi.spyOn(artifactsApi, 'update').mockResolvedValue({} as never);
      renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} onClose={() => undefined} />);
      await typeInNotes('# Typed');
      const field = screen.getByLabelText('Editor');
      fireEvent.click(screen.getByRole('button', { name: 'Full screen' }));
      const layer = await screen.findByRole('dialog', { name: 'Files, full screen' });
      expect(within(layer).getByLabelText('Editor')).toBe(field);
      expect(editorText()).toBe('# Typed');
      fireEvent.click(within(layer).getByRole('button', { name: 'Back' }));
      await waitFor(() =>
        expect(screen.queryByRole('dialog', { name: 'Files, full screen' })).toBeNull(),
      );
      expect(screen.getByLabelText('Editor')).toBe(field);
      expect(document.querySelector('.artifact-panel__body')?.contains(field)).toBe(true);
    });

    it('Escape leaves full screen', async () => {
      renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
      await openApp();
      fireEvent.click(screen.getByRole('button', { name: 'Full screen' }));
      const layer = await screen.findByRole('dialog', { name: 'Files, full screen' });
      fireEvent.keyDown(layer, { key: 'Escape' });
      await waitFor(() =>
        expect(screen.queryByRole('dialog', { name: 'Files, full screen' })).toBeNull(),
      );
    });
  });

  describe('a research plan that waits for a go-ahead', () => {
    const plan = [
      {
        id: 'p1',
        title: 'Research Plan',
        filename: 'Research Plan',
        type: 'file',
        language: 'markdown',
        file_system_type: 'research_plan_pending',
      },
    ];
    beforeEach(() => {
      vi.spyOn(artifactsApi, 'list').mockResolvedValue(plan as never);
      vi.spyOn(artifactsApi, 'get').mockResolvedValue({
        id: 'p1',
        title: 'Research Plan',
        language: 'markdown',
        content: '# Plan',
      } as never);
      useStreamStore.setState({
        chatId: 'c',
        live: {
          ...emptyLiveTurn(),
          pendingRequest: {
            id: 'call1',
            question: 'Do you approve of this research plan?',
            options: ['Yes, proceed'],
          },
        },
      });
    });

    it('Approve answers the waiting question', async () => {
      const respond = vi
        .spyOn(clarificationApi, 'respond')
        .mockResolvedValue(new Response(null) as never);
      renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
      fireEvent.click(await file(/^Research Plan/));
      fireEvent.click(await screen.findByRole('button', { name: 'Approve' }));
      await waitFor(() => expect(respond).toHaveBeenCalledWith('c', 'call1', 'Yes, proceed'));
    });

    it('Suggest changes sends what should change', async () => {
      const respond = vi
        .spyOn(clarificationApi, 'respond')
        .mockResolvedValue(new Response(null) as never);
      renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
      fireEvent.click(await file(/^Research Plan/));
      fireEvent.click(await screen.findByRole('button', { name: 'Suggest changes' }));
      expect(screen.getByRole('button', { name: 'Send changes' })).toBeDisabled();
      fireEvent.change(screen.getByLabelText('What should change?'), {
        target: { value: 'Compare three tools' },
      });
      fireEvent.click(screen.getByRole('button', { name: 'Send changes' }));
      await waitFor(() =>
        expect(respond).toHaveBeenCalledWith('c', 'call1', 'Compare three tools'),
      );
    });

    it('no go-ahead is offered on another file, or when nothing is waiting', async () => {
      useStreamStore.setState({ chatId: null, live: null });
      renderWithProviders(<ArtifactPanel scope={{ chatId: 'c' }} />);
      fireEvent.click(await file(/^Research Plan/));
      await screen.findByRole('heading', { name: 'Plan' });
      expect(screen.queryByRole('button', { name: 'Approve' })).toBeNull();
    });
  });
});
