import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, screen } from '@testing-library/react';
import { renderWithProviders } from '../../test/render';
import { ADMIN, USER, signInAs } from '../../test/roles';
import { DialogHost } from './DialogHost';
import { useModalStore } from '../../state/modal-store';
import { settingsApi } from '../../api/settings';

describe('DialogHost by role', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    useModalStore.setState({ open: null });
  });

  it.each(['agent-config', 'models', 'stealth', 'portal'] as const)('a user cannot open the admin dialog %s', (name) => {
    signInAs(USER);
    const agents = vi.spyOn(settingsApi, 'getAgents').mockResolvedValue({} as never);
    renderWithProviders(<DialogHost />);
    act(() => useModalStore.getState().show(name));
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(agents).not.toHaveBeenCalled();
  });

  it('a user can still open a per-user dialog', () => {
    signInAs(USER);
    vi.spyOn(settingsApi, 'getSystem').mockResolvedValue({} as never);
    vi.spyOn(settingsApi, 'version').mockResolvedValue({ version: '1' });
    renderWithProviders(<DialogHost />);
    act(() => useModalStore.getState().show('system-settings'));
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  it('the admin can open an admin dialog', () => {
    signInAs(ADMIN);
    vi.spyOn(settingsApi, 'getAgents').mockResolvedValue({} as never);
    renderWithProviders(<DialogHost />);
    act(() => useModalStore.getState().show('agent-config'));
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });
});
