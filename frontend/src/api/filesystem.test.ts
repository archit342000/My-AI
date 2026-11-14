import { afterEach, describe, expect, it, vi } from 'vitest';
import { artifactsApi, codeExecApi } from './filesystem';

type Call = [string, RequestInit | undefined];

function stub(body: unknown = {}) {
  const fetchMock = vi.fn(async () => new Response(JSON.stringify(body), { status: 200 }));
  vi.stubGlobal('fetch', fetchMock);
  return () => fetchMock.mock.calls[0] as unknown as Call;
}

afterEach(() => vi.unstubAllGlobals());

describe('artifactsApi file and directory calls', () => {
  it('list and get put the scope in the query, for a chat and a workspace', async () => {
    let call = stub({ file_systems: [] });
    await artifactsApi.list({ chatId: 'c1' });
    expect(call()[0]).toBe('/api/file_systems?chat_id=c1');
    call = stub({ file_systems: [] });
    await artifactsApi.list({ workspaceId: 'w1' });
    expect(call()[0]).toBe('/api/file_systems?workspace_id=w1');
    call = stub({ content: '' });
    await artifactsApi.get('a/b', { workspaceId: 'w1' });
    expect(call()[0]).toBe('/api/file_systems/a%2Fb?workspace_id=w1');
  });

  it('update (rename and move) PATCHes title or folder with the scope in the body', async () => {
    const call = stub();
    await artifactsApi.update('f1', { chatId: 'c1' }, { title: 'new.md' });
    const [url, init] = call();
    expect(url).toBe('/api/file_systems/f1');
    expect(init?.method).toBe('PATCH');
    expect(JSON.parse(String(init?.body))).toEqual({ chat_id: 'c1', title: 'new.md' });
  });

  it('createDirectory POSTs the path in the body and deleteDirectory DELETEs it in the query, for both scopes', async () => {
    let call = stub();
    await artifactsApi.createDirectory({ chatId: 'c1' }, 'notes/2026');
    expect(call()[0]).toBe('/api/file_systems/directory');
    expect(call()[1]?.method).toBe('POST');
    expect(JSON.parse(String(call()[1]?.body))).toEqual({ chat_id: 'c1', path: 'notes/2026' });
    call = stub();
    await artifactsApi.createDirectory({ workspaceId: 'w1' }, 'docs');
    expect(JSON.parse(String(call()[1]?.body))).toEqual({ workspace_id: 'w1', path: 'docs' });
    call = stub();
    await artifactsApi.deleteDirectory({ chatId: 'c1' }, 'notes/2026');
    expect(call()[0]).toBe('/api/file_systems/directory?chat_id=c1&path=notes%2F2026');
    expect(call()[1]?.method).toBe('DELETE');
    call = stub();
    await artifactsApi.deleteDirectory({ workspaceId: 'w1' }, 'docs');
    expect(call()[0]).toBe('/api/file_systems/directory?workspace_id=w1&path=docs');
  });

  it('a refused directory delete rejects with the server message', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(
        async () =>
          new Response(JSON.stringify({ error: 'Directory is not empty' }), { status: 400 }),
      ),
    );
    await expect(artifactsApi.deleteDirectory({ chatId: 'c1' }, 'full')).rejects.toMatchObject({
      message: 'Directory is not empty',
    });
  });
});

describe('artifactsApi version calls (chat scope)', () => {
  it('versions, version and currentVersion read the scope from the query', async () => {
    let call = stub({ versions: [] });
    await artifactsApi.versions('f1', { chatId: 'c1' });
    expect(call()[0]).toBe('/api/file_systems/f1/versions?chat_id=c1');
    call = stub({ content: 'x' });
    await artifactsApi.version('f1', 3, { chatId: 'c1' });
    expect(call()[0]).toBe('/api/file_systems/f1/versions/3?chat_id=c1');
    call = stub({ current_version: 4 });
    expect(await artifactsApi.currentVersion('f1', { chatId: 'c1' })).toBe(4);
    expect(call()[0]).toBe('/api/file_systems/f1/current-version?chat_id=c1');
  });

  it('restore and diff send chat_id in the body and workspace_id (when there is one) in the query', async () => {
    let call = stub();
    await artifactsApi.restore('f1', 2, { chatId: 'c1' });
    expect(call()[0]).toBe('/api/file_systems/f1/versions/2/restore');
    expect(JSON.parse(String(call()[1]?.body))).toEqual({ chat_id: 'c1' });
    call = stub();
    await artifactsApi.restore('f1', 2, { chatId: 'c1', workspaceId: 'w1' });
    expect(call()[0]).toBe('/api/file_systems/f1/versions/2/restore?workspace_id=w1');
    call = stub({
      added_lines: ['b'],
      removed_lines: ['a'],
      stats: { lines_added: 1, lines_removed: 1 },
    });
    const diff = await artifactsApi.diff('f1', 1, 2, { chatId: 'c1', workspaceId: 'w1' });
    expect(call()[0]).toBe('/api/file_systems/f1/diff?workspace_id=w1');
    expect(JSON.parse(String(call()[1]?.body))).toEqual({
      chat_id: 'c1',
      version1: 1,
      version2: 2,
    });
    expect(diff.added_lines).toEqual(['b']);
  });
});

describe('codeExecApi', () => {
  it('runFile posts the chat and the path, and returns what the run printed', async () => {
    const call = stub({ result: 'hello\n' });
    const out = await codeExecApi.runFile({ chatId: 'c1' }, 'src/app.py');
    const [url, init] = call();
    expect(url).toBe('/api/tools/code-execution/run-file');
    expect(init?.method).toBe('POST');
    expect(JSON.parse(String(init?.body))).toEqual({ chat_id: 'c1', path: 'src/app.py' });
    expect(out).toBe('hello\n');
  });

  it('runFile posts the workspace in place of a chat', async () => {
    const call = stub({ result: 'ok' });
    await codeExecApi.runFile({ workspaceId: 'w1' }, 'a.py');
    expect(JSON.parse(String(call()[1]?.body))).toEqual({ workspace_id: 'w1', path: 'a.py' });
  });
});
