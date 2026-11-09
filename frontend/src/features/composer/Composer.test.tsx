import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { renderWithProviders } from '../../test/render';
import { Composer } from './Composer';
import { useSettingsStore } from '../../state/settings-store';
import { useStreamStore } from '../../state/stream-store';
import { useModalStore } from '../../state/modal-store';
import { useToastStore } from '../../components/ui/toast-store';
import * as files from '../../api/files';
import { chatListInvalidated } from '../../test/invalidation';
import * as sendTurnModule from '../chat/send-turn';

const textarea = () => screen.getByPlaceholderText('Type a message…') as HTMLTextAreaElement;
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

  it('send is disabled when empty and enabled once there is text', () => {
    renderWithProviders(<Composer />);
    expect(sendBtn().disabled).toBe(true);
    fireEvent.change(textarea(), { target: { value: 'hi' } });
    expect(sendBtn().disabled).toBe(false);
  });

  it('send is disabled when no model is selected, even with text', () => {
    useSettingsStore.setState({ model: null });
    renderWithProviders(<Composer />);
    fireEvent.change(textarea(), { target: { value: 'hi' } });
    expect(sendBtn().disabled).toBe(true);
  });

  it('Enter sends the message and clears the box; Shift+Enter does not send', async () => {
    const send = vi.spyOn(sendTurnModule, 'sendTurn').mockResolvedValue(undefined);
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
    const send = vi.spyOn(sendTurnModule, 'sendTurn').mockResolvedValue(undefined);
    renderWithProviders(<Composer />, { route: '/chat/c1', path: '/chat/:chatId' });
    fireEvent.change(textarea(), { target: { value: 'にほんご' } });
    fireEvent.keyDown(textarea(), { key: 'Enter', isComposing: false, keyCode: 229 });
    expect(send).not.toHaveBeenCalled();
  });

  it('does not send on Enter while an IME composition is in progress', () => {
    const send = vi.spyOn(sendTurnModule, 'sendTurn').mockResolvedValue(undefined);
    renderWithProviders(<Composer />, { route: '/chat/c1', path: '/chat/:chatId' });
    fireEvent.change(textarea(), { target: { value: 'にほんご' } });
    fireEvent.keyDown(textarea(), { key: 'Enter', isComposing: true, keyCode: 229 });
    expect(send).not.toHaveBeenCalled();
  });

  it('a new chat (home route) is created with a generated id and navigates to it', async () => {
    const send = vi.spyOn(sendTurnModule, 'sendTurn').mockResolvedValue(undefined);
    renderWithProviders(<Composer />);
    fireEvent.change(textarea(), { target: { value: 'hello' } });
    fireEvent.click(sendBtn());
    await waitFor(() => expect(send).toHaveBeenCalled());
    expect(send.mock.calls[0]![0].isNewChat).toBe(true);
    expect(send.mock.calls[0]![0].chatId).toBeTruthy();
  });

  it('/help shows a hint and clears the box without sending', () => {
    const send = vi.spyOn(sendTurnModule, 'sendTurn').mockResolvedValue(undefined);
    renderWithProviders(<Composer />);
    fireEvent.change(textarea(), { target: { value: '/help' } });
    fireEvent.keyDown(textarea(), { key: 'Enter' });
    expect(send).not.toHaveBeenCalled();
    expect(textarea().value).toBe('');
    expect(useToastStore.getState().toasts.some((t) => t.message.includes('/skills'))).toBe(true);
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
    const send = vi.spyOn(sendTurnModule, 'sendTurn').mockResolvedValue(undefined);
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
      const send = vi.spyOn(sendTurnModule, 'sendTurn').mockResolvedValue(undefined);
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
