import { QueryClient } from '@tanstack/react-query';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { chatsApi } from '../../api/chats';
import { useUiStore } from '../../state/ui-store';
import { saveTemporaryChat, shouldDiscardTemporaryChat } from './temporary-chat';

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
    expect(patch).toHaveBeenCalledWith('t1', expect.objectContaining({ title: 'hello there' }));
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
