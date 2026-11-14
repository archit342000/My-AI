import { QueryClient } from '@tanstack/react-query';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { chatsApi } from '../../api/chats';
import { useUiStore } from '../../state/ui-store';
import { useStreamStore } from '../../state/stream-store';
import {
  discardTemporaryChat,
  saveTemporaryChat,
  shouldDiscardTemporaryChat,
} from './temporary-chat';

describe('discardTemporaryChat', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    useUiStore.setState({ temporaryChatId: null });
    useStreamStore.setState({
      chatId: null,
      live: null,
      pending: null,
      interrupted: null,
      controller: null,
      stopping: false,
    });
  });

  it('stops a turn that is still generating before it deletes the chat', async () => {
    const order: string[] = [];
    useUiStore.setState({ temporaryChatId: 't9' });
    useStreamStore.setState({ chatId: 't9', controller: new AbortController() });
    vi.spyOn(chatsApi, 'stop').mockImplementation(async () => {
      order.push('stop');
      // temporary mode is still on while the turn is being stopped (no Send over a busy store)
      expect(useUiStore.getState().temporaryChatId).toBe('t9');
      // the turn ends once the stop is answered
      useStreamStore.getState().finish();
      return new Response(null);
    });
    vi.spyOn(chatsApi, 'remove').mockImplementation(async () => {
      order.push('delete');
      return new Response(null);
    });
    await discardTemporaryChat(new QueryClient());
    expect(order).toEqual(['stop', 'delete']);
  });

  it('a temporary chat started while the previous one is still being discarded is discarded too', async () => {
    useUiStore.setState({ temporaryChatId: 'A' });
    let releaseA: () => void = () => undefined;
    const gateA = new Promise<void>((resolve) => (releaseA = resolve));
    const remove = vi.spyOn(chatsApi, 'remove').mockImplementation(async (id: string) => {
      if (id === 'A') await gateA;
      return new Response(null);
    });
    const client = new QueryClient();
    const first = discardTemporaryChat(client);
    await vi.waitFor(() => expect(remove).toHaveBeenCalledWith('A')); // temporary mode is off, delete of A pending
    expect(useUiStore.getState().temporaryChatId).toBeNull();
    useUiStore.setState({ temporaryChatId: 'B' }); // the user starts another temporary chat
    await discardTemporaryChat(client);
    expect(remove).toHaveBeenCalledWith('B');
    releaseA();
    await first;
  });

  it('two discards at once delete the chat once', async () => {
    useUiStore.setState({ temporaryChatId: 't9' });
    const remove = vi.spyOn(chatsApi, 'remove').mockResolvedValue(new Response(null));
    const client = new QueryClient();
    await Promise.all([discardTemporaryChat(client), discardTemporaryChat(client)]);
    expect(remove).toHaveBeenCalledTimes(1);
  });

  it('just deletes a temporary chat that is not generating', async () => {
    useUiStore.setState({ temporaryChatId: 't9' });
    const stop = vi.spyOn(chatsApi, 'stop');
    const remove = vi.spyOn(chatsApi, 'remove').mockResolvedValue(new Response(null));
    await discardTemporaryChat(new QueryClient());
    expect(stop).not.toHaveBeenCalled();
    expect(remove).toHaveBeenCalledWith('t9');
  });
});

describe('saveTemporaryChat', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    useUiStore.setState({ temporaryChatId: null });
  });

  it('titles the chat from its first message, leaves temporary mode and returns the id', async () => {
    const patch = vi.spyOn(chatsApi, 'patch').mockResolvedValue({} as never);
    useUiStore.setState({ temporaryChatId: 't1' });
    const id = await saveTemporaryChat(new QueryClient(), 'hello there');
    expect(id).toBe('t1');
    expect(patch).toHaveBeenCalledWith(
      't1',
      expect.objectContaining({ title: 'hello there', is_temporary: false }),
    );
    expect(useUiStore.getState().temporaryChatId).toBeNull();
  });

  it('does nothing outside temporary mode', async () => {
    const patch = vi.spyOn(chatsApi, 'patch').mockResolvedValue({} as never);
    expect(await saveTemporaryChat(new QueryClient(), 'x')).toBeNull();
    expect(patch).not.toHaveBeenCalled();
  });
});

describe('shouldDiscardTemporaryChat (F-10)', () => {
  it('keeps a temporary chat started from a chat page when the move to / commits', () => {
    expect(shouldDiscardTemporaryChat('/chat/x', '/', true)).toBe(false);
  });
  it('discards it when the user leaves the landing page', () => {
    expect(shouldDiscardTemporaryChat('/', '/chat/y', true)).toBe(true);
  });
  it('does nothing without a temporary chat or without a navigation', () => {
    expect(shouldDiscardTemporaryChat('/', '/chat/y', false)).toBe(false);
    expect(shouldDiscardTemporaryChat('/chat/x', '/chat/x', true)).toBe(false);
  });
});
