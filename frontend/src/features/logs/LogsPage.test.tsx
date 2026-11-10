import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { renderWithProviders } from '../../test/render';
import { ADMIN, USER, signInAs } from '../../test/roles';
import { LogsPage } from './LogsPage';
import { logsApi } from './logsApi';

describe('LogsPage by role', () => {
  afterEach(() => vi.restoreAllMocks());

  it('a user sees "Not available" and no logs request is made', async () => {
    signInAs(USER);
    const stream = vi.spyOn(logsApi, 'stream').mockResolvedValue([]);
    const tables = vi
      .spyOn(logsApi, 'dbTables')
      .mockResolvedValue({ chat_tables: [], global_tables: [] });
    renderWithProviders(<LogsPage />);
    expect(screen.getByText('Not available')).toBeInTheDocument();
    await new Promise((r) => setTimeout(r, 20));
    expect(stream).not.toHaveBeenCalled();
    expect(tables).not.toHaveBeenCalled();
  });

  it('the admin gets the viewer and its request', async () => {
    signInAs(ADMIN);
    const stream = vi.spyOn(logsApi, 'stream').mockResolvedValue([]);
    renderWithProviders(<LogsPage />);
    expect(screen.queryByText('Not available')).toBeNull();
    await vi.waitFor(() => expect(stream).toHaveBeenCalled());
  });
});

describe('LogsPage expanded rows', () => {
  afterEach(() => vi.restoreAllMocks());

  it('keeps the same row open when a refresh puts a new row in front of it', async () => {
    signInAs(ADMIN);
    const older = { timestamp: '2026-11-10T10:00:00', url: '/api/older', status: 200 };
    const newer = { timestamp: '2026-11-10T10:00:05', url: '/api/newer', status: 201 };
    const stream = vi.spyOn(logsApi, 'stream').mockResolvedValue([older]);
    const { client } = renderWithProviders(<LogsPage />);
    const row = await screen.findByRole('button', { name: /\/api\/older/ });
    expect(row.getAttribute('aria-expanded')).toBe('false');
    fireEvent.click(row);
    expect(row.getAttribute('aria-expanded')).toBe('true');
    expect(document.querySelector('.logs-json')?.textContent).toContain('/api/older');
    stream.mockResolvedValue([newer, older]);
    await client.invalidateQueries({ queryKey: ['logs'] });
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /\/api\/newer/ })).toBeInTheDocument(),
    );
    // exactly one detail row, and it still belongs to the older entry
    const details = document.querySelectorAll('.logs-json');
    expect(details).toHaveLength(1);
    expect(details[0]?.textContent).toContain('/api/older');
    expect(details[0]?.textContent).not.toContain('/api/newer');
  });

  it('a row is one line with its time, name and the rest; opening it shows the whole entry and a way to the chat', async () => {
    signInAs(ADMIN);
    vi.spyOn(logsApi, 'stream').mockResolvedValue([
      {
        timestamp: '2026-11-10T14:01:31',
        method: 'POST',
        url: '/v1/chat',
        status: 200,
        chat_id: 'c9',
        body: { a: 1 },
      },
    ]);
    renderWithProviders(<LogsPage />);
    const row = await screen.findByRole('button', { name: /POST/ });
    expect(row).toHaveTextContent('14:01');
    expect(row).toHaveTextContent('/v1/chat · 200 · c9');
    expect(screen.queryByRole('link', { name: 'Open the chat' })).toBeNull();
    fireEvent.click(row);
    expect(document.querySelector('.logs-json')?.textContent).toContain('"a": 1');
    expect(screen.getByRole('link', { name: 'Open the chat' }).getAttribute('href')).toBe(
      '/chat/c9',
    );
    fireEvent.click(row);
    expect(document.querySelector('.logs-json')).toBeNull();
  });
});

describe('LogsPage filter, count and states', () => {
  afterEach(() => vi.restoreAllMocks());
  const lines = ['INFO server started', 'ERROR could not reach the model', 'WARNING slow answer'];

  it('says how many entries there are, and how many of them match the filter', async () => {
    signInAs(ADMIN);
    vi.spyOn(logsApi, 'stream').mockResolvedValue(lines);
    renderWithProviders(<LogsPage />);
    fireEvent.click(await screen.findByRole('radio', { name: 'App' }));
    expect(await screen.findByText('3 entries')).toBeTruthy();
    fireEvent.change(screen.getByLabelText('Filter entries'), { target: { value: 'MODEL' } });
    expect(screen.getByText('1 of 3 entries')).toBeTruthy();
    expect(screen.getByRole('button', { name: /could not reach the model/ })).toBeTruthy();
    fireEvent.change(screen.getByLabelText('Filter entries'), { target: { value: 'zzz' } });
    expect(screen.getByText('Nothing matches')).toBeTruthy();
  });

  it('the app log can be narrowed to chosen levels', async () => {
    signInAs(ADMIN);
    vi.spyOn(logsApi, 'stream').mockResolvedValue(lines);
    renderWithProviders(<LogsPage />);
    fireEvent.click(await screen.findByRole('radio', { name: 'App' }));
    await screen.findByText('3 entries');
    const error = screen.getByRole('button', { name: 'Error' });
    fireEvent.click(error);
    expect(error.getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByText('1 of 3 entries')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Warning' }));
    expect(screen.getByText('2 of 3 entries')).toBeTruthy();
  });

  it('shows placeholder rows while loading, then says so when nothing is logged', async () => {
    signInAs(ADMIN);
    let release: (v: unknown[]) => void = () => undefined;
    vi.spyOn(logsApi, 'stream').mockImplementation(
      () => new Promise((resolve) => (release = resolve)),
    );
    renderWithProviders(<LogsPage />);
    expect(screen.getByRole('status', { name: 'Loading the log' })).toBeTruthy();
    release([]);
    expect(await screen.findByText('Nothing logged yet')).toBeTruthy();
  });

  it('a log that cannot be loaded says why and offers to try again', async () => {
    signInAs(ADMIN);
    const stream = vi.spyOn(logsApi, 'stream').mockRejectedValue(new Error('log file missing'));
    renderWithProviders(<LogsPage />);
    expect(await screen.findByRole('alert')).toHaveTextContent('log file missing');
    stream.mockResolvedValue(['INFO back']);
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    expect(await screen.findByText('1 entry')).toBeTruthy();
  });

  it('the database log waits for a chat id before it asks for rows', async () => {
    signInAs(ADMIN);
    vi.spyOn(logsApi, 'stream').mockResolvedValue([]);
    vi.spyOn(logsApi, 'dbTables').mockResolvedValue({ chat_tables: ['chats'], global_tables: [] });
    const rows = vi.spyOn(logsApi, 'dbRows').mockResolvedValue([{ id: 4, title: 'Fix the test' }]);
    renderWithProviders(<LogsPage />);
    fireEvent.click(await screen.findByRole('radio', { name: 'Database' }));
    expect(screen.getByText('Enter a chat id')).toBeTruthy();
    expect(rows).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText('Chat id'), { target: { value: 'c1' } });
    expect(await screen.findByRole('button', { name: /Fix the test/ })).toBeTruthy();
    expect(rows).toHaveBeenCalledWith('chats', 'c1', 100);
  });
});
