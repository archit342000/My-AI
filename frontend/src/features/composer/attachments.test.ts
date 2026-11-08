import { describe, expect, it } from 'vitest';
import {
  allReady,
  attachmentStatusLabel,
  MAX_CONCURRENT_UPLOADS,
  nextToUpload,
  toUploadedFiles,
  type Attachment,
} from './attachments';

function item(key: string, patch: Partial<Attachment> = {}): Attachment {
  return {
    key,
    name: `${key}.txt`,
    size: 10,
    mimeType: 'text/plain',
    file: new File(['x'], `${key}.txt`),
    chatId: 'c1',
    status: 'queued',
    progress: 0,
    uploaded: null,
    error: null,
    ...patch,
  };
}

describe('nextToUpload', () => {
  it('limits concurrent uploads and counts processing files as busy', () => {
    const items = [
      item('a', { status: 'uploading' }),
      item('b', { status: 'processing' }),
      item('c'),
      item('d'),
    ];
    expect(MAX_CONCURRENT_UPLOADS).toBe(2);
    expect(nextToUpload(items)).toEqual([]);
  });

  it('starts queued files in order up to the free slots', () => {
    const items = [item('a', { status: 'ready' }), item('b'), item('c'), item('d')];
    expect(nextToUpload(items).map((a) => a.key)).toEqual(['b', 'c']);
  });
});

describe('send gating', () => {
  it('blocks sending until every chip is ready, and only sends ready files', () => {
    const ready = item('a', { status: 'ready', uploaded: { file_id: 'f1', name: 'a.txt', size: 1, mime_type: 'text/plain' } });
    const failed = item('b', { status: 'error', error: 'boom' });
    expect(allReady([ready, failed])).toBe(false);
    expect(allReady([ready])).toBe(true);
    expect(toUploadedFiles([ready, failed]).map((f) => f.file_id)).toEqual(['f1']);
  });
});

describe('attachmentStatusLabel', () => {
  it('describes each lifecycle state', () => {
    expect(attachmentStatusLabel(item('a', { status: 'uploading', progress: 0.42 }))).toBe('Uploading 42%');
    expect(attachmentStatusLabel(item('a', { status: 'processing', progress: 1 }))).toBe('Processing…');
    expect(attachmentStatusLabel(item('a', { status: 'ready' }))).toBe('Ready');
    expect(attachmentStatusLabel(item('a', { status: 'error', error: 'Too big' }))).toBe('Too big');
  });
});
