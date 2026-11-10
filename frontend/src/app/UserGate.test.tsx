import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { UserGate } from './UserGate';
import { useSettingsStore } from '../state/settings-store';
import { useUserStore } from '../state/user-store';
import { resetUserStorage } from '../lib/user-storage';

function mockMe(response: () => Response) {
  const fetchMock = vi.fn(async () => response());
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

function renderGate() {
  // The app's own default is retry: 1; UserGate must still not retry a 401.
  const client = new QueryClient({ defaultOptions: { queries: { retry: 1, retryDelay: 1 } } });
  return render(
    <QueryClientProvider client={client}>
      <UserGate>
        <div data-testid="app">app</div>
      </UserGate>
    </QueryClientProvider>,
  );
}

describe('UserGate', () => {
  beforeEach(() => {
    localStorage.clear();
    useUserStore.setState({ user: null, sessionExpired: false });
    resetUserStorage();
  });
  afterEach(() => vi.unstubAllGlobals());

  it('shows a loading state, then the app with the user recorded', async () => {
    mockMe(() => json({ id: 'u1', email: 'u1@x.io', role: 'user' }));
    renderGate();
    expect(screen.queryByTestId('app')).toBeNull();
    expect(screen.getByRole('status')).toHaveTextContent('Loading');
    expect(await screen.findByTestId('app')).toBeInTheDocument();
    expect(useUserStore.getState().user).toEqual({ id: 'u1', email: 'u1@x.io', role: 'user' });
  });

  it('never renders the app before /api/me has answered', async () => {
    let release: (r: Response) => void = () => undefined;
    vi.stubGlobal(
      'fetch',
      vi.fn(() => new Promise<Response>((resolve) => (release = resolve))),
    );
    renderGate();
    await new Promise((r) => setTimeout(r, 20));
    expect(screen.queryByTestId('app')).toBeNull();
    release(json({ id: 'u1', email: 'u1@x.io', role: 'user' }));
    expect(await screen.findByTestId('app')).toBeInTheDocument();
  });

  it("loads the user's own saved settings before the app renders", async () => {
    localStorage.setItem('my_ai_selected_model:u1', 'model-of-u1');
    localStorage.setItem('my_ai_selected_model', 'model-of-admin');
    mockMe(() => json({ id: 'u1', email: 'u1@x.io', role: 'user' }));
    renderGate();
    await screen.findByTestId('app');
    expect(useSettingsStore.getState().model).toBe('model-of-u1');
  });

  it('gives the admin the existing key names', async () => {
    localStorage.setItem('my_ai_selected_model', 'model-of-admin');
    mockMe(() => json({ id: 'a1', email: 'a@x.io', role: 'admin' }));
    renderGate();
    await screen.findByTestId('app');
    expect(useSettingsStore.getState().model).toBe('model-of-admin');
  });

  it('shows the session-expired message after a single request on a 401', async () => {
    const fetchMock = mockMe(() => json({ error: 'Unauthorized' }, 401));
    renderGate();
    expect(await screen.findByText('Your session has ended.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Sign in again' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Show details' })).toBeNull();
    expect(screen.queryByTestId('app')).toBeNull();
    await new Promise((r) => setTimeout(r, 30));
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('shows the generic error on a server error', async () => {
    mockMe(() => json({ error: 'boom' }, 500));
    renderGate();
    await waitFor(() =>
      expect(screen.getByText("Couldn't load your account.")).toBeInTheDocument(),
    );
    expect(screen.queryByTestId('app')).toBeNull();
    // The way forward is a button; the server's own words stay behind Show details.
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Show details' })).toBeInTheDocument();
  });
});
