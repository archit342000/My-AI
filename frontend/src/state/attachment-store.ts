import { create } from 'zustand';
import { deleteFile } from '../api/files';
import { showToast } from '../components/ui/toast-store';
import type { Attachment } from '../features/composer/attachments';
import { generateChatId } from '../lib/chat-id';

/**
 * Files staged for sending, kept per chat. The key is the chat they were uploaded for: an open chat's id, the
 * temporary chat's id, or `draftChatId` for the next new chat. A chip therefore only shows in its own chat, and
 * a draft that is never sent can be thrown away together with the files already uploaded for it.
 */
interface AttachmentState {
  lists: Record<string, Attachment[]>;
  /** The id the next new chat will get; its staged files are uploaded for it. Renewed after a send or a discard. */
  draftChatId: string;
  /** Local keys of chips thrown away while their upload ran: the file is deleted when it lands. */
  doomed: Record<string, true>;
  add: (key: string, items: Attachment[]) => void;
  update: (key: string, attachmentKey: string, patch: Partial<Attachment>) => void;
  remove: (key: string, attachmentKey: string) => void;
  clear: (key: string) => void;
  renewDraft: () => void;
  markDoomed: (attachmentKey: string) => void;
  /** True once if the chip was thrown away while uploading (and forgets it). */
  takeDoomed: (attachmentKey: string) => boolean;
  /** Throws a key's staged files away: uploaded ones are deleted on the server, running uploads are doomed. */
  discard: (key: string, options?: { keepalive?: boolean }) => Promise<void>;
}

export const useAttachmentStore = create<AttachmentState>((set, get) => ({
  lists: {},
  draftChatId: generateChatId(),
  doomed: {},
  add: (key, items) =>
    set((s) => ({ lists: { ...s.lists, [key]: [...(s.lists[key] ?? []), ...items] } })),
  update: (key, attachmentKey, patch) =>
    set((s) => {
      const list = s.lists[key];
      if (!list) return s;
      return {
        lists: {
          ...s.lists,
          [key]: list.map((a) => (a.key === attachmentKey ? { ...a, ...patch } : a)),
        },
      };
    }),
  remove: (key, attachmentKey) =>
    set((s) => {
      const list = s.lists[key];
      if (!list) return s;
      return { lists: { ...s.lists, [key]: list.filter((a) => a.key !== attachmentKey) } };
    }),
  clear: (key) =>
    set((s) => {
      if (!(key in s.lists)) return s;
      const rest = { ...s.lists };
      delete rest[key];
      return { lists: rest };
    }),
  renewDraft: () => set({ draftChatId: generateChatId() }),
  markDoomed: (attachmentKey) => set((s) => ({ doomed: { ...s.doomed, [attachmentKey]: true } })),
  takeDoomed: (attachmentKey) => {
    if (!get().doomed[attachmentKey]) return false;
    set((s) => {
      const rest = { ...s.doomed };
      delete rest[attachmentKey];
      return { doomed: rest };
    });
    return true;
  },
  discard: async (key, options = {}) => {
    const items = get().lists[key] ?? [];
    if (items.length === 0) return;
    get().clear(key);
    const deletions: Array<Promise<void>> = [];
    for (const item of items) {
      if (item.uploaded) deletions.push(deleteFile(item.uploaded.file_id, options));
      else if (item.status === 'uploading' || item.status === 'processing')
        get().markDoomed(item.key);
    }
    const results = await Promise.allSettled(deletions);
    const failed = results.filter((r) => r.status === 'rejected').length;
    if (failed > 0) showToast(`Could not remove ${failed} uploaded file${failed > 1 ? 's' : ''}`, 'error');
  },
}));
