import { afterEach, describe, expect, it, vi } from 'vitest';
import * as filesApi from '../api/files';
import type { Attachment } from '../features/composer/attachments';
import { useToastStore } from '../components/ui/toast-store';
import { useAttachmentStore } from './attachment-store';

const chip = (key: string, status: Attachment['status'], fileId?: string): Attachment => ({
  key,
  name: key,
  size: 1,
  mimeType: 'text/plain',
  file: new File(['x'], key),
  chatId: 'c',
  status,
  progress: status === 'ready' ? 1 : 0,
  uploaded: fileId ? { file_id: fileId, name: key, size: 1, mime_type: 'text/plain' } : null,
  error: null,
});

afterEach(() => {
  vi.restoreAllMocks();
  useAttachmentStore.setState({ lists: {}, doomed: {} });
});

describe('attachment store', () => {
  it('keeps a separate list per chat key', () => {
    const { add, remove, update } = useAttachmentStore.getState();
    add('a', [chip('1', 'queued')]);
    add('b', [chip('2', 'queued')]);
    update('a', '1', { status: 'ready' });
    expect(useAttachmentStore.getState().lists['a']?.[0]?.status).toBe('ready');
    expect(useAttachmentStore.getState().lists['b']?.[0]?.status).toBe('queued');
    remove('b', '2');
    expect(useAttachmentStore.getState().lists['b']).toEqual([]);
  });

  it('clear forgets one key only', () => {
    const { add, clear } = useAttachmentStore.getState();
    add('a', [chip('1', 'ready')]);
    add('b', [chip('2', 'ready')]);
    clear('a');
    expect(Object.keys(useAttachmentStore.getState().lists)).toEqual(['b']);
  });

  it('discard deletes the uploaded files of that key only and empties it', async () => {
    const del = vi.spyOn(filesApi, 'deleteFile').mockResolvedValue(undefined);
    const { add, discard } = useAttachmentStore.getState();
    add('a', [chip('1', 'ready', 'f1'), chip('2', 'ready', 'f2')]);
    add('b', [chip('3', 'ready', 'f3')]);
    await discard('a');
    expect(del.mock.calls.map((c) => c[0])).toEqual(['f1', 'f2']);
    expect(useAttachmentStore.getState().lists['a']).toBeUndefined();
    expect(useAttachmentStore.getState().lists['b']).toHaveLength(1);
  });

  it('a file still uploading is doomed, so it is deleted when it lands; a queued one is just dropped', async () => {
    const del = vi.spyOn(filesApi, 'deleteFile').mockResolvedValue(undefined);
    const { add, discard } = useAttachmentStore.getState();
    add('a', [chip('up', 'uploading'), chip('proc', 'processing'), chip('q', 'queued')]);
    await discard('a');
    expect(del).not.toHaveBeenCalled();
    const { takeDoomed } = useAttachmentStore.getState();
    expect(takeDoomed('up')).toBe(true);
    expect(takeDoomed('up')).toBe(false); // only once
    expect(takeDoomed('proc')).toBe(true);
    expect(takeDoomed('q')).toBe(false);
  });

  it('passes keepalive to the delete', async () => {
    const del = vi.spyOn(filesApi, 'deleteFile').mockResolvedValue(undefined);
    useAttachmentStore.getState().add('a', [chip('1', 'ready', 'f1')]);
    await useAttachmentStore.getState().discard('a', { keepalive: true });
    expect(del).toHaveBeenCalledWith('f1', { keepalive: true });
  });

  it('a failed delete does not stop the others and is reported; discard of an empty key does nothing', async () => {
    const del = vi
      .spyOn(filesApi, 'deleteFile')
      .mockRejectedValueOnce(new Error('nope'))
      .mockResolvedValue(undefined);
    useAttachmentStore.getState().add('a', [chip('1', 'ready', 'f1'), chip('2', 'ready', 'f2')]);
    await useAttachmentStore.getState().discard('a');
    expect(del).toHaveBeenCalledTimes(2);
    expect(useToastStore.getState().toasts.some((t) => t.message === 'Could not remove 1 uploaded file')).toBe(true);
    await useAttachmentStore.getState().discard('empty');
    expect(del).toHaveBeenCalledTimes(2);
  });

  it('renewDraft gives the next new chat a different id', () => {
    const before = useAttachmentStore.getState().draftChatId;
    useAttachmentStore.getState().renewDraft();
    expect(useAttachmentStore.getState().draftChatId).not.toBe(before);
  });
});
