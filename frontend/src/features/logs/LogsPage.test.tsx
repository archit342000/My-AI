import { afterEach, describe, expect, it, vi } from 'vitest';
import { screen } from '@testing-library/react';
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
