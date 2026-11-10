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
    const tables = vi.spyOn(logsApi, 'dbTables').mockResolvedValue({ chat_tables: [], global_tables: [] });
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
    const row = await screen.findByText('/api/older');
    fireEvent.click(row);
    expect(document.querySelector('.logs-json')?.textContent).toContain('/api/older');
    stream.mockResolvedValue([newer, older]);
    await client.invalidateQueries({ queryKey: ['logs'] });
    await waitFor(() => expect(screen.getByText('/api/newer')).toBeInTheDocument());
    // exactly one detail row, and it still belongs to the older entry
    const details = document.querySelectorAll('.logs-json');
    expect(details).toHaveLength(1);
    expect(details[0]?.textContent).toContain('/api/older');
    expect(details[0]?.textContent).not.toContain('/api/newer');
  });
});
