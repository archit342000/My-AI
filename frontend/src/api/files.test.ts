import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from './client';
import { deleteFile } from './files';

afterEach(() => vi.unstubAllGlobals());

describe('deleteFile', () => {
  it('sends DELETE /api/files/<encoded id>', async () => {
    const fetchMock = vi.fn(async () => new Response('{}', { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);
    await deleteFile('file/1 x');
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe('/api/files/file%2F1%20x');
    expect(init.method).toBe('DELETE');
  });

  it('throws an ApiError with the server message on a non-2xx response', async () => {
    const body = JSON.stringify({ error: 'File not found' });
    vi.stubGlobal('fetch', vi.fn(async () => new Response(body, { status: 404 })));
    await expect(deleteFile('missing')).rejects.toBeInstanceOf(ApiError);
    await expect(deleteFile('missing')).rejects.toMatchObject({
      status: 404,
      message: 'File not found',
    });
  });
});
