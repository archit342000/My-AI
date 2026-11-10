import { renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import * as filesApi from '../../api/files';
import { useAttachmentStore } from '../../state/attachment-store';
import { useDraftCleanup } from './useDraftCleanup';

const ready = (fileId: string) => ({
  key: fileId,
  name: fileId,
  size: 1,
  mimeType: 'text/plain',
  file: new File(['x'], fileId),
  chatId: 'c',
  status: 'ready' as const,
  progress: 1,
  uploaded: { file_id: fileId, name: fileId, size: 1, mime_type: 'text/plain' },
  error: null,
});

function pagehide(persisted: boolean) {
  const event = new Event('pagehide') as PageTransitionEvent;
  Object.defineProperty(event, 'persisted', { value: persisted });
  window.dispatchEvent(event);
}

afterEach(() => vi.restoreAllMocks());

describe('useDraftCleanup', () => {
  it('a real page hide deletes every unsent file with keepalive', () => {
    const del = vi.spyOn(filesApi, 'deleteFile').mockResolvedValue(undefined);
    useAttachmentStore.getState().add('a', [ready('f1')]);
    useAttachmentStore.getState().add('b', [ready('f2')]);
    renderHook(() => useDraftCleanup());
    pagehide(false);
    expect(del).toHaveBeenCalledWith('f1', { keepalive: true });
    expect(del).toHaveBeenCalledWith('f2', { keepalive: true });
  });

  it('a hide into the back/forward cache deletes nothing', () => {
    const del = vi.spyOn(filesApi, 'deleteFile').mockResolvedValue(undefined);
    useAttachmentStore.getState().add('a', [ready('f1')]);
    renderHook(() => useDraftCleanup());
    pagehide(true);
    expect(del).not.toHaveBeenCalled();
  });

  it('stops listening when unmounted', () => {
    const del = vi.spyOn(filesApi, 'deleteFile').mockResolvedValue(undefined);
    useAttachmentStore.getState().add('a', [ready('f1')]);
    renderHook(() => useDraftCleanup()).unmount();
    pagehide(false);
    expect(del).not.toHaveBeenCalled();
  });
});
