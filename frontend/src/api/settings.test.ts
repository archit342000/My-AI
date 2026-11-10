import { afterEach, describe, expect, it, vi } from 'vitest';
import { settingsApi } from './settings';

function stubFetch() {
  const fetchMock = vi.fn<typeof fetch>(
    async () =>
      new Response('{}', { status: 200, headers: { 'Content-Type': 'application/json' } }),
  );
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}
const sent = (fetchMock: ReturnType<typeof stubFetch>) => {
  const call = fetchMock.mock.calls[0];
  return {
    path: call?.[0],
    method: call?.[1]?.method,
    body: JSON.parse(String(call?.[1]?.body)) as unknown,
  };
};

describe('git settings calls', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('saveGitToken posts only the token', async () => {
    const fetchMock = stubFetch();
    await settingsApi.saveGitToken('ghp_secret');
    expect(sent(fetchMock)).toEqual({
      path: '/api/tools/config/settings',
      method: 'POST',
      body: { github_pat: 'ghp_secret' },
    });
  });

  it('saveGitAllowedCommands posts the full list', async () => {
    const fetchMock = stubFetch();
    await settingsApi.saveGitAllowedCommands(['status', 'diff']);
    expect(sent(fetchMock)).toEqual({
      path: '/api/tools/config/settings',
      method: 'POST',
      body: { git_allowed_commands: ['status', 'diff'] },
    });
  });

  it('getSystem reads the settings including the git fields', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({
              github_pat_configured: true,
              git_known_commands: ['status'],
              git_allowed_commands: [],
            }),
            {
              status: 200,
              headers: { 'Content-Type': 'application/json' },
            },
          ),
      ),
    );
    const system = await settingsApi.getSystem();
    expect(system.github_pat_configured).toBe(true);
    expect(system.git_known_commands).toEqual(['status']);
  });
});
