import type { UploadedFile } from '../../api/completions';

/** Lifecycle of one attachment chip: queued → uploading → processing → ready (or error). */
export type AttachmentStatus = 'queued' | 'uploading' | 'processing' | 'ready' | 'error';

export interface Attachment {
  /** Local key, stable across retries (the server id only exists once uploaded). */
  key: string;
  name: string;
  size: number;
  mimeType: string;
  file: File;
  chatId: string;
  status: AttachmentStatus;
  /** Upload fraction 0..1 while `uploading`. */
  progress: number;
  uploaded: UploadedFile | null;
  error: string | null;
}

/** Simultaneous uploads per composer. Two keeps the server responsive and the chips moving. */
export const MAX_CONCURRENT_UPLOADS = 2;

/** Attachments that should start uploading now, respecting the concurrency limit. */
export function nextToUpload(items: readonly Attachment[], limit = MAX_CONCURRENT_UPLOADS): Attachment[] {
  const busy = items.filter((a) => a.status === 'uploading' || a.status === 'processing').length;
  const free = Math.max(0, limit - busy);
  return items.filter((a) => a.status === 'queued').slice(0, free);
}

/** Only ready files are sent with the message; a chip still in flight blocks sending. */
export function allReady(items: readonly Attachment[]): boolean {
  return items.every((a) => a.status === 'ready');
}

export function toUploadedFiles(items: readonly Attachment[]): UploadedFile[] {
  return items.flatMap((a) => (a.status === 'ready' && a.uploaded ? [a.uploaded] : []));
}

/** Short label shown on a chip next to its name. */
export function attachmentStatusLabel(a: Attachment): string {
  switch (a.status) {
    case 'queued':
      return 'Waiting';
    case 'uploading':
      return `Uploading ${Math.round(a.progress * 100)}%`;
    case 'processing':
      return 'Processing…';
    case 'ready':
      return 'Ready';
    case 'error':
      return a.error ?? 'Failed';
  }
}

export function isImageType(mimeType: string): boolean {
  return mimeType.startsWith('image/');
}
