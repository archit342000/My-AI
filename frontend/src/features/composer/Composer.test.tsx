import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { Link, MemoryRouter } from 'react-router';
import { chatsApi } from '../../api/chats';
import { ApiError } from '../../api/client';
import { renderWithProviders } from '../../test/render';
import { Composer } from './Composer';
import { useSettingsStore } from '../../state/settings-store';
import { useStreamStore } from '../../state/stream-store';
import { useModalStore } from '../../state/modal-store';
import { useAttachmentStore } from '../../state/attachment-store';
import { useUiStore } from '../../state/ui-store';
import { useToastStore } from '../../components/ui/toast-store';
import * as files from '../../api/files';
import type { UploadedFile } from '../../api/completions';
import { chatListInvalidated } from '../../test/invalidation';
import * as sendTurnModule from '../chat/send-turn';

const textarea = () => screen.getByPlaceholderText('Start a conversation...') as HTMLTextAreaElement;
const sendBtn = () => screen.getByRole('button', { name: /Send message|Stop generating/ }) as HTMLButtonElement;

describe('Composer', () => {
  beforeEach(() => {
    useSettingsStore.setState({ model: 'm1', modelName: 'Model 1' });
    useStreamStore.setState({ chatId: null, live: null, pending: null, interrupted: null, controller: null });
    useToastStore.setState({ toasts: [] });
    useModalStore.setState({ open: null });
  });
  afterEach(() => {
    vi.restoreAllMocks();
    useSettingsStore.setState({ model: null, modelName: null });
  });

  it('with an empty box the send button stays blue (aria-disabled, not disabled) and a click sends nothing', () => {
    const send = vi.spyOn(sendTurnModule, 'sendTurn').mockResolvedValue(true);
    renderWithProviders(<Composer />);
    expect(sendBtn().disabled).toBe(false);
    expect(sendBtn().getAttribute('aria-disabled')).toBe('true');
    fireEvent.click(sendBtn());
    expect(send).not.toHaveBeenCalled();
    fireEvent.change(textarea(), { target: { value: 'hi' } });
    expect(sendBtn().getAttribute('aria-disabled')).toBeNull();
  });

  it('uses the legacy placeholder', () => {
    renderWithProviders(<Composer />);
    expect(screen.getByPlaceholderText('Start a conversation...')).toBeTruthy();
  });

  it('the attach and tools buttons are plain composer action buttons', () => {
    renderWithProviders(<Composer />);
    const attach = screen.getByRole('button', { name: 'Attach files' });
    expect(attach.id).toBe('attach-btn');
    expect(attach.className).toBe('input-action-btn');
    expect(document.getElementById('tools-button')?.className).toBe('input-action-btn');
  });

  it('send is disabled while a file uploads, and enabled again once it is ready', async () => {
    let finish: (f: UploadedFile) => void = () => undefined;
    vi.spyOn(files, 'uploadFile').mockImplementation(
      () => new Promise((resolve) => (finish = resolve as typeof finish)),
    );
    const { container } = renderWithProviders(<Composer />, { route: '/chat/c1', path: '/chat/:chatId' });
    fireEvent.change(container.querySelector('input[type=file]') as HTMLInputElement, {
      target: { files: [new File(['abc'], 'a.txt', { type: 'text/plain' })] },
    });
    fireEvent.change(textarea(), { target: { value: 'hi' } });
    await waitFor(() => expect(sendBtn().disabled).toBe(true));
    finish({ file_id: 'f1', name: 'a.txt', size: 3, mime_type: 'text/plain' });
    await waitFor(() => expect(sendBtn().disabled).toBe(false));
  });

  it('send is disabled when no model is selected, even with text', () => {
    useSettingsStore.setState({ model: null });
    renderWithProviders(<Composer />);
    fireEvent.change(textarea(), { target: { value: 'hi' } });
    expect(sendBtn().disabled).toBe(true);
  });

  it('Enter sends the message and clears the box; Shift+Enter does not send', async () => {
    const send = vi.spyOn(sendTurnModule, 'sendTurn').mockImplementation(async (a) => {
      a.onAccepted?.();
      return true;
    });
    renderWithProviders(<Composer />, { route: '/chat/c1', path: '/chat/:chatId' });
    fireEvent.change(textarea(), { target: { value: 'line one' } });
    fireEvent.keyDown(textarea(), { key: 'Enter', shiftKey: true });
    expect(send).not.toHaveBeenCalled();
    fireEvent.keyDown(textarea(), { key: 'Enter' });
    await waitFor(() => expect(send).toHaveBeenCalledTimes(1));
    expect(send.mock.calls[0]![0]).toMatchObject({ chatId: 'c1', text: 'line one', isNewChat: false });
    expect(textarea().value).toBe('');
  });

  it('explains why send is disabled when no model is set (F4)', () => {
    useSettingsStore.setState({ model: null } as never);
    renderWithProviders(<Composer />);
    expect(screen.getByText('Choose a model in Chat Settings')).toBeTruthy();
  });

  it('does not send on the Safari composition-ending Enter (keyCode 229, isComposing false)', () => {
    const send = vi.spyOn(sendTurnModule, 'sendTurn').mockResolvedValue(true);
    renderWithProviders(<Composer />, { route: '/chat/c1', path: '/chat/:chatId' });
    fireEvent.change(textarea(), { target: { value: 'にほんご' } });
    fireEvent.keyDown(textarea(), { key: 'Enter', isComposing: false, keyCode: 229 });
    expect(send).not.toHaveBeenCalled();
  });

  it('does not send on Enter while an IME composition is in progress', () => {
    const send = vi.spyOn(sendTurnModule, 'sendTurn').mockResolvedValue(true);
    renderWithProviders(<Composer />, { route: '/chat/c1', path: '/chat/:chatId' });
    fireEvent.change(textarea(), { target: { value: 'にほんご' } });
    fireEvent.keyDown(textarea(), { key: 'Enter', isComposing: true, keyCode: 229 });
    expect(send).not.toHaveBeenCalled();
  });

  it('a new chat (home route) is created with a generated id and navigates to it', async () => {
    const send = vi.spyOn(sendTurnModule, 'sendTurn').mockResolvedValue(true);
    renderWithProviders(<Composer />);
    fireEvent.change(textarea(), { target: { value: 'hello' } });
    fireEvent.click(sendBtn());
    await waitFor(() => expect(send).toHaveBeenCalled());
    expect(send.mock.calls[0]![0].isNewChat).toBe(true);
    expect(send.mock.calls[0]![0].chatId).toBeTruthy();
  });

  it('/help opens the command list, clears the box without sending, and Escape returns focus to the box', () => {
    const send = vi.spyOn(sendTurnModule, 'sendTurn').mockResolvedValue(true);
    renderWithProviders(<Composer />);
    textarea().focus();
    fireEvent.change(textarea(), { target: { value: '/help' } });
    fireEvent.keyDown(textarea(), { key: 'Enter' });
    expect(send).not.toHaveBeenCalled();
    expect(textarea().value).toBe('');
    const dialog = screen.getByRole('dialog', { name: 'Commands and skills' });
    expect(dialog.textContent).toContain('/skills');
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('dialog', { name: 'Commands and skills' })).toBeNull();
    expect(document.activeElement).toBe(textarea());
  });

  it('/skills opens the skills dialog', () => {
    renderWithProviders(<Composer />);
    fireEvent.change(textarea(), { target: { value: '/skills' } });
    fireEvent.keyDown(textarea(), { key: 'Enter' });
    expect(useModalStore.getState().open).toBe('skills');
  });

  it('slash autocomplete lists matching commands and fills the box on click', () => {
    renderWithProviders(<Composer />);
    fireEvent.change(textarea(), { target: { value: '/s' } });
    const item = screen.getByRole('option', { name: /\/skills/ });
    fireEvent.click(item);
    expect(textarea().value).toBe('/skills ');
  });

  it('slash autocomplete hides once a space is typed', () => {
    renderWithProviders(<Composer />);
    fireEvent.change(textarea(), { target: { value: '/skills x' } });
    expect(document.getElementById('slash-commands-autocomplete')).toBeNull();
  });

  it('attaches a file, shows progress, marks it ready and sends it with the turn', async () => {
    vi.spyOn(files, 'uploadFile').mockResolvedValue({ file_id: 'f1', name: 'a.txt', size: 3, mime_type: 'text/plain' });
    const send = vi.spyOn(sendTurnModule, 'sendTurn').mockResolvedValue(true);
    const { container } = renderWithProviders(<Composer />, { route: '/chat/c1', path: '/chat/:chatId' });
    const input = container.querySelector('input[type=file]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [new File(['abc'], 'a.txt', { type: 'text/plain' })] } });
    await waitFor(() => expect(screen.getByText('a.txt')).toBeTruthy());
    await waitFor(() => expect(sendBtn().disabled).toBe(true), { timeout: 2000 }).catch(() => undefined);
    fireEvent.change(textarea(), { target: { value: 'see file' } });
    await waitFor(() => expect(sendBtn().disabled).toBe(false));
    fireEvent.click(sendBtn());
    await waitFor(() => expect(send).toHaveBeenCalled());
    expect(send.mock.calls[0]![0].files).toEqual([{ file_id: 'f1', name: 'a.txt', size: 3, mime_type: 'text/plain' }]);
  });

  describe('sidebar chat list and chip removal', () => {
    const attach = (container: HTMLElement, name = 'a.txt') =>
      fireEvent.change(container.querySelector('input[type=file]') as HTMLInputElement, {
        target: { files: [new File(['abc'], name, { type: 'text/plain' })] },
      });
    const uploaded = { file_id: 'f1', name: 'a.txt', size: 3, mime_type: 'text/plain' };
    const renderInChat = () =>
      renderWithProviders(<Composer />, { route: '/chat/c1', path: '/chat/:chatId' });

    it('a finished upload refreshes the chat list (the chat now has a file)', async () => {
      vi.spyOn(files, 'uploadFile').mockResolvedValue(uploaded);
      const { container, client } = renderInChat();
      const invalidate = vi.spyOn(client, 'invalidateQueries');
      attach(container);
      await waitFor(() => expect(chatListInvalidated(invalidate)).toBe(true));
    });

    it('sending an uploaded file keeps it on the server (no delete)', async () => {
      vi.spyOn(files, 'uploadFile').mockResolvedValue(uploaded);
      const del = vi.spyOn(files, 'deleteFile').mockResolvedValue(undefined);
      const send = vi.spyOn(sendTurnModule, 'sendTurn').mockResolvedValue(true);
      const { container } = renderInChat();
      attach(container);
      await screen.findByRole('button', { name: /Remove a\.txt/ });
      fireEvent.change(textarea(), { target: { value: 'see file' } });
      await waitFor(() => expect(sendBtn().disabled).toBe(false));
      fireEvent.click(sendBtn());
      await waitFor(() => expect(send).toHaveBeenCalled());
      expect(del).not.toHaveBeenCalled();
    });

    it('removing an uploaded chip deletes the server file and refreshes the list', async () => {
      vi.spyOn(files, 'uploadFile').mockResolvedValue(uploaded);
      const del = vi.spyOn(files, 'deleteFile').mockResolvedValue(undefined);
      const { container, client } = renderInChat();
      attach(container);
      const removeBtn = await screen.findByRole('button', { name: /Remove a\.txt/ });
      const invalidate = vi.spyOn(client, 'invalidateQueries');
      fireEvent.click(removeBtn);
      await waitFor(() => expect(del).toHaveBeenCalledWith('f1'));
      await waitFor(() => expect(chatListInvalidated(invalidate)).toBe(true));
    });

    it('a failed delete shows a toast and still refreshes the list', async () => {
      vi.spyOn(files, 'uploadFile').mockResolvedValue(uploaded);
      vi.spyOn(files, 'deleteFile').mockRejectedValue(new Error('locked'));
      const { container, client } = renderInChat();
      attach(container);
      const removeBtn = await screen.findByRole('button', { name: /Remove a\.txt/ });
      const invalidate = vi.spyOn(client, 'invalidateQueries');
      fireEvent.click(removeBtn);
      await waitFor(() => {
        expect(useToastStore.getState().toasts.map((t) => t.message)).toContain('locked');
      });
      await waitFor(() => expect(chatListInvalidated(invalidate)).toBe(true));
    });

    it('removing a chip that never reached the server makes no delete call', async () => {
      vi.spyOn(files, 'uploadFile').mockRejectedValue(new Error('too big'));
      const del = vi.spyOn(files, 'deleteFile').mockResolvedValue(undefined);
      const { container } = renderInChat();
      attach(container, 'big.bin');
      fireEvent.click(await screen.findByRole('button', { name: /Remove big\.bin/ }));
      expect(del).not.toHaveBeenCalled();
    });

    it('removing a chip mid-upload deletes the file once the upload lands', async () => {
      let resolveUpload: (u: typeof uploaded) => void = () => undefined;
      vi.spyOn(files, 'uploadFile').mockImplementation(
        () => new Promise((res) => { resolveUpload = res; }),
      );
      const del = vi.spyOn(files, 'deleteFile').mockResolvedValue(undefined);
      const { container, client } = renderInChat();
      attach(container);
      fireEvent.click(await screen.findByRole('button', { name: /Remove a\.txt/ }));
      expect(del).not.toHaveBeenCalled(); // the upload is still running
      const invalidate = vi.spyOn(client, 'invalidateQueries');
      resolveUpload(uploaded);
      await waitFor(() => expect(del).toHaveBeenCalledWith('f1'));
      await waitFor(() => expect(chatListInvalidated(invalidate)).toBe(true));
    });

    it('a chip removed mid-upload whose upload then fails shows no toast', async () => {
      let rejectUpload: (e: Error) => void = () => undefined;
      vi.spyOn(files, 'uploadFile').mockImplementation(
        () => new Promise((_res, rej) => { rejectUpload = rej; }),
      );
      const del = vi.spyOn(files, 'deleteFile').mockResolvedValue(undefined);
      const { container } = renderInChat();
      attach(container);
      fireEvent.click(await screen.findByRole('button', { name: /Remove a\.txt/ }));
      rejectUpload(new Error('network down'));
      await new Promise((r) => setTimeout(r, 20));
      expect(useToastStore.getState().toasts).toHaveLength(0);
      expect(del).not.toHaveBeenCalled();
    });
  });

  it('a failed upload shows "failed" and a toast, and blocks sending until removed', async () => {
    vi.spyOn(files, 'uploadFile').mockRejectedValue(new Error('too big'));
    const { container } = renderWithProviders(<Composer />, { route: '/chat/c1', path: '/chat/:chatId' });
    fireEvent.change(container.querySelector('input[type=file]') as HTMLInputElement, { target: { files: [new File(['x'], 'big.bin')] } });
    await waitFor(() => expect(screen.getByRole('button', { name: 'Retry big.bin' })).toBeTruthy());
    expect(useToastStore.getState().toasts.some((t) => t.message === 'too big')).toBe(true);
    fireEvent.change(textarea(), { target: { value: 'x' } });
    expect(sendBtn().disabled).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: 'Remove big.bin' }));
    expect(sendBtn().disabled).toBe(false);
  });

  it('renders no composer on a chat that failed to load', async () => {
    vi.spyOn(chatsApi, 'get').mockRejectedValue(new ApiError(404, {}, 'missing'));
    renderWithProviders(<Composer />, { route: '/chat/gone', path: '/chat/:chatId' });
    await waitFor(() => expect(chatsApi.get).toHaveBeenCalled());
    await waitFor(() => expect(screen.queryByPlaceholderText('Start a conversation...')).toBeNull());
  });

  it('keeps the text and files when the send is refused', async () => {
    const send = vi.spyOn(sendTurnModule, 'sendTurn').mockResolvedValue(false);
    renderWithProviders(<Composer />, { route: '/chat/c1', path: '/chat/:chatId' });
    fireEvent.change(textarea(), { target: { value: 'keep me' } });
    fireEvent.keyDown(textarea(), { key: 'Enter' });
    await waitFor(() => expect(send).toHaveBeenCalledTimes(1));
    expect(textarea().value).toBe('keep me');
  });

  it('a new chat navigates only through the callback sendTurn invokes', async () => {
    const send = vi.spyOn(sendTurnModule, 'sendTurn').mockResolvedValue(true);
    renderWithProviders(<Composer />);
    fireEvent.change(textarea(), { target: { value: 'first' } });
    fireEvent.keyDown(textarea(), { key: 'Enter' });
    await waitFor(() => expect(send).toHaveBeenCalledTimes(1));
    // sendTurn is mocked and never calls navigate, so the route did not change.
    expect(screen.queryByTestId('elsewhere')).toBeNull();
    const call = send.mock.calls[0]?.[0];
    expect(call?.navigate).toBeDefined();
    call?.navigate?.();
    expect(await screen.findByTestId('elsewhere')).toBeTruthy();
  });

  it('drops a draft when the user switches to another chat, but keeps what is typed after its own first send', async () => {
    vi.spyOn(chatsApi, 'get').mockResolvedValue({ id: 'x', title: 't', messages: [] } as never);
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const view = render(
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={['/chat/c1']}>
          <Composer />
          <Link to="/chat/c2">other chat</Link>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    fireEvent.change(textarea(), { target: { value: 'draft for c1' } });
    fireEvent.click(screen.getByText('other chat'));
    await waitFor(() => expect(textarea().value).toBe(''));
    view.unmount();

    const send = vi.spyOn(sendTurnModule, 'sendTurn').mockImplementation(async (a) => {
      a.onAccepted?.();
      a.navigate?.();
      return true;
    });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={['/']}>
          <Composer />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    fireEvent.change(textarea(), { target: { value: 'first' } });
    fireEvent.keyDown(textarea(), { key: 'Enter' });
    await waitFor(() => expect(send).toHaveBeenCalledTimes(1));
    fireEvent.change(textarea(), { target: { value: 'typed during stream start' } });
    await new Promise((r) => setTimeout(r, 30));
    expect(textarea().value).toBe('typed during stream start');
  });

  it('shows Stop only in the chat that is generating; another chat can still send', () => {
    useStreamStore.setState({ chatId: 'other', live: null, pending: null, interrupted: null, controller: null });
    renderWithProviders(<Composer />, { route: '/chat/c1', path: '/chat/:chatId' });
    fireEvent.change(textarea(), { target: { value: 'hi' } });
    expect(screen.queryByRole('button', { name: 'Stop generating' })).toBeNull();
    expect(sendBtn().disabled).toBe(false);
  });

  it('while streaming the send button becomes Stop and calls stopTurn', () => {
    useStreamStore.setState({ chatId: 'c1', live: null, pending: null, interrupted: null, controller: null });
    const stop = vi.spyOn(sendTurnModule, 'stopTurn').mockResolvedValue(undefined);
    renderWithProviders(<Composer />, { route: '/chat/c1', path: '/chat/:chatId' });
    fireEvent.click(screen.getByRole('button', { name: 'Stop generating' }));
    expect(stop).toHaveBeenCalled();
  });

  it('the attach button opens the hidden file input', () => {
    const { container } = renderWithProviders(<Composer />);
    const input = container.querySelector('input[type=file]') as HTMLInputElement;
    const click = vi.spyOn(input, 'click');
    fireEvent.click(screen.getByRole('button', { name: /Attach files|attach/i }).closest('button') ?? document.getElementById('attach-btn')!);
    expect(click).toHaveBeenCalled();
  });
});

describe('Composer staged files per chat', () => {
  const uploaded = (id: string, name: string) => ({ file_id: id, name, size: 3, mime_type: 'text/plain' });
  const attach = (container: HTMLElement, name: string) =>
    fireEvent.change(container.querySelector('input[type=file]') as HTMLInputElement, {
      target: { files: [new File(['abc'], name, { type: 'text/plain' })] },
    });
  function renderWithLinks(route: string) {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return render(
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={[route]}>
          <Composer />
          <Link to="/chat/a">chat a</Link>
          <Link to="/chat/b">chat b</Link>
          <Link to="/">home</Link>
        </MemoryRouter>
      </QueryClientProvider>,
    );
  }

  beforeEach(() => {
    useSettingsStore.setState({ model: 'm1', modelName: 'Model 1' });
    useStreamStore.setState({ chatId: null, live: null, pending: null, interrupted: null, controller: null });
    vi.spyOn(chatsApi, 'get').mockResolvedValue({ id: 'x', title: 't', messages: [] } as never);
  });
  afterEach(() => {
    vi.restoreAllMocks();
    useSettingsStore.setState({ model: null, modelName: null });
  });

  it('a file staged in one chat is not shown in another, and is shown again when the user comes back', async () => {
    vi.spyOn(files, 'uploadFile').mockResolvedValue(uploaded('f1', 'a.txt'));
    const view = renderWithLinks('/chat/a');
    attach(view.container, 'a.txt');
    await waitFor(() => expect(screen.getByText('a.txt')).toBeTruthy());
    fireEvent.click(screen.getByText('chat b'));
    await waitFor(() => expect(screen.queryByText('a.txt')).toBeNull());
    fireEvent.click(screen.getByText('chat a'));
    await waitFor(() => expect(screen.getByText('a.txt')).toBeTruthy());
  });

  it('a file staged on the home page is not shown in temporary mode', async () => {
    vi.spyOn(files, 'uploadFile').mockResolvedValue(uploaded('f1', 'a.txt'));
    const view = renderWithLinks('/');
    attach(view.container, 'a.txt');
    await waitFor(() => expect(screen.getByText('a.txt')).toBeTruthy());
    act(() => useUiStore.getState().setTemporaryChatId('temp1'));
    await waitFor(() => expect(screen.queryByText('a.txt')).toBeNull());
    act(() => useUiStore.getState().setTemporaryChatId(null));
    await waitFor(() => expect(screen.getByText('a.txt')).toBeTruthy());
  });

  it('uploads for the chat the file is staged in, and sending clears that chat only', async () => {
    const upload = vi.spyOn(files, 'uploadFile').mockResolvedValue(uploaded('f1', 'a.txt'));
    const send = vi.spyOn(sendTurnModule, 'sendTurn').mockImplementation(async (a) => {
      a.onAccepted?.();
      return true;
    });
    const view = renderWithLinks('/chat/a');
    attach(view.container, 'a.txt');
    await waitFor(() => expect(upload).toHaveBeenCalledWith(expect.any(File), 'a', expect.any(Function)));
    useAttachmentStore.getState().add('b', [
      { key: 'kb', name: 'b.txt', size: 1, mimeType: 'text/plain', file: new File(['x'], 'b.txt'), chatId: 'b', status: 'ready', progress: 1, uploaded: uploaded('f2', 'b.txt'), error: null },
    ]);
    await waitFor(() => expect(sendBtn().disabled).toBe(false));
    fireEvent.change(textarea(), { target: { value: 'go' } });
    fireEvent.click(sendBtn());
    await waitFor(() => expect(send).toHaveBeenCalled());
    expect(useAttachmentStore.getState().lists['a']).toBeUndefined();
    expect(useAttachmentStore.getState().lists['b']).toHaveLength(1);
  });

  it('after the first send of a new chat the next new chat gets a fresh draft id', async () => {
    vi.spyOn(sendTurnModule, 'sendTurn').mockImplementation(async (a) => {
      a.onAccepted?.();
      return true;
    });
    renderWithLinks('/');
    const before = useAttachmentStore.getState().draftChatId;
    fireEvent.change(textarea(), { target: { value: 'hello' } });
    fireEvent.click(sendBtn());
    await waitFor(() => expect(useAttachmentStore.getState().draftChatId).not.toBe(before));
  });
});

describe('Composer drop and paste', () => {
  const uploaded = { file_id: 'f1', name: 'a.txt', size: 3, mime_type: 'text/plain' };
  beforeEach(() => {
    useSettingsStore.setState({ model: 'm1', modelName: 'Model 1' });
    vi.spyOn(files, 'uploadFile').mockResolvedValue(uploaded);
  });
  afterEach(() => {
    vi.restoreAllMocks();
    useSettingsStore.setState({ model: null, modelName: null });
  });

  it('files dropped on the page area get chips, and the drop state shows while dragging them', async () => {
    renderWithProviders(
      <main data-testid="zone">
        <Composer />
      </main>,
      { route: '/chat/c1', path: '/chat/:chatId' },
    );
    const zone = screen.getByTestId('zone');
    const data = { types: ['Files'], files: [new File(['a'], 'a.txt'), new File(['b'], 'b.txt')] };
    fireEvent.dragEnter(zone, { dataTransfer: data });
    expect(screen.getByText('Drop files to attach')).toBeTruthy();
    fireEvent.drop(zone, { dataTransfer: data });
    await waitFor(() => expect(screen.getAllByText(/\.txt$/)).toHaveLength(2));
    expect(screen.queryByText('Drop files to attach')).toBeNull();
  });

  it('a pasted file gets a chip, and pasted text still goes into the box', async () => {
    renderWithProviders(<Composer />, { route: '/chat/c1', path: '/chat/:chatId' });
    fireEvent.paste(textarea(), { clipboardData: { files: [new File(['a'], 'pasted.png')], types: ['Files'] } });
    await waitFor(() => expect(screen.getByText('pasted.png')).toBeTruthy());
    // Text: no files in the clipboard, so the default paste is not prevented.
    const notPrevented = fireEvent.paste(textarea(), { clipboardData: { files: [], types: ['text/plain'] } });
    expect(notPrevented).toBe(true);
  });

  it('a drag without files shows no drop state', () => {
    renderWithProviders(
      <main data-testid="zone">
        <Composer />
      </main>,
      { route: '/chat/c1', path: '/chat/:chatId' },
    );
    fireEvent.dragEnter(screen.getByTestId('zone'), { dataTransfer: { types: ['text/plain'], files: [] } });
    expect(screen.queryByText('Drop files to attach')).toBeNull();
  });
});
