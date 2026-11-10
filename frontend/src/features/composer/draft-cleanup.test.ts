import { QueryClient } from '@tanstack/react-query';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { chatsApi } from '../../api/chats';
import * as filesApi from '../../api/files';
import { useAttachmentStore } from '../../state/attachment-store';
import { discardNewChatDraft } from './draft-cleanup';

const ready = (key: string, fileId: string) => ({
  key,
  name: key,
  size: 1,
  mimeType: 'text/plain',
  file: new File(['x'], key),
  chatId: 'd',
  status: 'ready' as const,
  progress: 1,
  uploaded: { file_id: fileId, name: key, size: 1, mime_type: 'text/plain' },
  error: null,
});

afterEach(() => vi.restoreAllMocks());

describe('discardNewChatDraft', () => {
  it('still refreshes the list when the chat row is already gone (404)', async () => {
    vi.spyOn(filesApi, 'deleteFile').mockResolvedValue(undefined);
    vi.spyOn(chatsApi, 'remove').mockRejectedValue(new Error('404'));
    const client = new QueryClient();
    const invalidate = vi.spyOn(client, 'invalidateQueries');
    const key = useAttachmentStore.getState().draftChatId;
    useAttachmentStore.getState().add(key, [ready('1', 'f1')]);
    await discardNewChatDraft(client);
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['chats'] });
  });

  it("deletes the draft's uploaded files, renews the draft id and refreshes the chat list", async () => {
    const del = vi.spyOn(filesApi, 'deleteFile').mockResolvedValue(undefined);
    const remove = vi.spyOn(chatsApi, 'remove').mockResolvedValue(new Response(null));
    const client = new QueryClient();
    const invalidate = vi.spyOn(client, 'invalidateQueries');
    const key = useAttachmentStore.getState().draftChatId;
    useAttachmentStore.getState().add(key, [ready('1', 'f1')]);
    await discardNewChatDraft(client);
    expect(del).toHaveBeenCalledWith('f1', {});
    expect(remove).toHaveBeenCalledWith(key); // the skeleton chat row the upload created
    expect(useAttachmentStore.getState().draftChatId).not.toBe(key);
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['chats'] });
  });

  it("does nothing when no file is staged, and leaves an existing chat's files alone", async () => {
    const del = vi.spyOn(filesApi, 'deleteFile').mockResolvedValue(undefined);
    const client = new QueryClient();
    const invalidate = vi.spyOn(client, 'invalidateQueries');
    const before = useAttachmentStore.getState().draftChatId;
    useAttachmentStore.getState().add('some-chat', [ready('1', 'f1')]);
    await discardNewChatDraft(client);
    expect(del).not.toHaveBeenCalled();
    expect(invalidate).not.toHaveBeenCalled();
    expect(useAttachmentStore.getState().draftChatId).toBe(before);
    expect(useAttachmentStore.getState().lists['some-chat']).toHaveLength(1);
  });
});
