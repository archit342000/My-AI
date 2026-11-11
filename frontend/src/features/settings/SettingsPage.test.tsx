import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes, useLocation, useNavigationType } from 'react-router';
import { modelsApi, personasApi, preferencesApi, settingsApi, skillsApi } from '../../api/settings';
import { markSaved, resetSaveLight } from '../../lib/save-light';
import { ADMIN, USER, signInAs } from '../../test/roles';
import { SettingsPage } from './SettingsPage';
import { sectionFromSearch, searchWithSection, useOpenSettings } from './settings-nav';

/** A page with a button that opens the settings, and the settings page over it when the address says so. */
function Under() {
  const location = useLocation();
  const how = useNavigationType();
  const open = useOpenSettings();
  return (
    <div>
      <p>the page beneath</p>
      <button onClick={() => open('system')}>open system</button>
      <output data-testid="address">{location.pathname + location.search}</output>
      <output data-testid="how">{how}</output>
      {sectionFromSearch(location.search) ? <SettingsPage /> : null}
    </div>
  );
}

function renderAt(entry: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[entry]}>
        <Routes>
          <Route path="*" element={<Under />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
/** How the last move was made: PUSH adds a step to go back over, REPLACE does not. */
const how = () => screen.getByTestId('how').textContent;
const address = () => screen.getByTestId('address').textContent;
const list = () => within(screen.getByRole('navigation', { name: 'Settings sections' }));

describe('settings addresses', () => {
  it('reads the part from the address; an unknown one opens at Chat; none means closed', () => {
    expect(sectionFromSearch('?settings=models')).toBe('models');
    expect(sectionFromSearch('?settings=nonsense')).toBe('chat');
    expect(sectionFromSearch('?settings=')).toBe('chat');
    expect(sectionFromSearch('?other=1')).toBeNull();
  });

  it('adds, changes and removes the part while keeping the rest of the address', () => {
    expect(searchWithSection('', 'skills')).toBe('?settings=skills');
    expect(searchWithSection('?a=1&settings=chat', 'system')).toBe('?a=1&settings=system');
    expect(searchWithSection('?a=1&settings=chat', null)).toBe('?a=1');
    expect(searchWithSection('?settings=chat', null)).toBe('');
  });
});

describe('SettingsPage', () => {
  beforeEach(() => {
    signInAs(ADMIN);
    resetSaveLight();
    vi.spyOn(modelsApi, 'list').mockResolvedValue([]);
    vi.spyOn(personasApi, 'list').mockResolvedValue([]);
    vi.spyOn(skillsApi, 'list').mockResolvedValue([]);
    vi.spyOn(preferencesApi, 'list').mockResolvedValue([]);
    vi.spyOn(settingsApi, 'getAgents').mockResolvedValue({});
    vi.spyOn(settingsApi, 'getBrowser').mockResolvedValue({ stealth_level: 'minimal' });
    vi.spyOn(settingsApi, 'getSystem').mockResolvedValue({
      code_runner_timeout: 30,
      code_runner_memory_limit: '512M',
      code_runner_cpu_limit: '1',
      code_runner_max_output_size: 65536,
    });
    vi.spyOn(settingsApi, 'version').mockResolvedValue({ version: '9.9.9' });
  });
  afterEach(() => vi.restoreAllMocks());

  it('marks the page while it is open, so the panels beside it step aside, and clears the mark after', () => {
    const { unmount } = renderAt('/?settings=chat');
    expect(document.documentElement.dataset.settings).toBe('open');
    unmount();
    expect(document.documentElement.dataset.settings).toBeUndefined();
  });

  it('is a page with Back, its seven parts listed and all in one column', () => {
    renderAt('/chat/c1?settings=chat');
    const page = screen.getByRole('region', { name: 'Settings' });
    expect(within(page).getByRole('heading', { level: 1, name: 'Settings' })).toBeTruthy();
    expect(within(page).getByRole('button', { name: 'Back' })).toBeTruthy();
    const names = ['Chat', 'Models', 'Personas', 'Skills', 'Memory', 'Agents', 'System'];
    expect(
      list()
        .getAllByRole('button')
        .map((b) => b.textContent),
    ).toEqual(names);
    expect(
      within(page)
        .getAllByRole('heading', { level: 2 })
        .map((h) => h.textContent),
    ).toEqual(names);
    expect(screen.queryByRole('dialog')).toBeNull(); // a page, not a pop-up
  });

  it("a user gets five parts: models and agents are the admin's, and their data is never asked for", async () => {
    signInAs(USER);
    renderAt('/?settings=models'); // asks for a part that is not theirs: opens at Chat
    expect(
      list()
        .getAllByRole('button')
        .map((b) => b.textContent),
    ).toEqual(['Chat', 'Personas', 'Skills', 'Memory', 'System']);
    expect(list().getByRole('button', { name: 'Chat' }).getAttribute('aria-current')).toBe('true');
    await screen.findByText(/Version 9\.9\.9/);
    expect(settingsApi.getAgents).not.toHaveBeenCalled();
    expect(settingsApi.getBrowser).not.toHaveBeenCalled();
    expect(settingsApi.getSystem).not.toHaveBeenCalled();
  });

  it('opens at the part the address names, and the list moves the address without adding steps', () => {
    renderAt('/chat/c1?settings=system');
    expect(list().getByRole('button', { name: 'System' }).getAttribute('aria-current')).toBe(
      'true',
    );
    fireEvent.click(list().getByRole('button', { name: 'Skills' }));
    expect(address()).toBe('/chat/c1?settings=skills');
    expect(list().getByRole('button', { name: 'Skills' }).getAttribute('aria-current')).toBe(
      'true',
    );
    expect(how()).toBe('REPLACE');
  });

  it('opened from the page beneath, Back returns to it exactly', async () => {
    renderAt('/chat/c1?keep=1');
    fireEvent.click(screen.getByRole('button', { name: 'open system' }));
    expect(address()).toBe('/chat/c1?keep=1&settings=system');
    expect(how()).toBe('PUSH');
    expect(screen.getByText('the page beneath')).toBeTruthy(); // still there underneath
    fireEvent.click(list().getByRole('button', { name: 'Memory' }));
    fireEvent.click(screen.getByRole('button', { name: 'Back' }));
    await waitFor(() => expect(address()).toBe('/chat/c1?keep=1'));
    expect(screen.queryByRole('region', { name: 'Settings' })).toBeNull();
  });

  it('reached by its address, Back just closes it', async () => {
    renderAt('/?settings=memory');
    fireEvent.click(screen.getByRole('button', { name: 'Back' }));
    await waitFor(() => expect(address()).toBe('/'));
  });

  it('Escape leaves the page', async () => {
    renderAt('/?settings=chat');
    fireEvent.keyDown(document, { key: 'Escape' });
    await waitFor(() => expect(screen.queryByRole('region', { name: 'Settings' })).toBeNull());
  });

  it('the light in the header shows nothing at first and Saved once something was changed', async () => {
    renderAt('/?settings=chat');
    const head = screen.getByRole('heading', { level: 1, name: 'Settings' })
      .parentElement as HTMLElement;
    expect(within(head).queryByRole('status')).toBeNull();
    markSaved();
    expect(await within(head).findByRole('status')).toHaveTextContent('Saved');
  });
});
