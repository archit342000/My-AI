import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { renderWithProviders } from '../../test/render';
import { ArtifactPanel } from './ArtifactPanel';
import { artifactsApi } from '../../api/filesystem';
import { chatListInvalidated } from '../../test/invalidation';
import { useToastStore } from '../../components/ui/toast-store';

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
  afterEach(() => vi.restoreAllMocks());

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
});
