import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, screen } from '@testing-library/react';
import { codeExecApi, portalApi } from '../../api/filesystem';
import { useModalStore } from '../../state/modal-store';
import { renderWithProviders } from '../../test/render';
import { ADMIN, USER, signInAs } from '../../test/roles';
import { DialogHost } from './DialogHost';

describe('DialogHost by role', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    useModalStore.setState({ open: null });
  });

  it('a user cannot open the browser window (admin only)', () => {
    signInAs(USER);
    const init = vi.spyOn(portalApi, 'init').mockResolvedValue({});
    renderWithProviders(<DialogHost />);
    act(() => useModalStore.getState().show('portal'));
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(init).not.toHaveBeenCalled();
  });

  it('a user can open the code run history', () => {
    signInAs(USER);
    vi.spyOn(codeExecApi, 'history').mockResolvedValue([]);
    renderWithProviders(<DialogHost />, { route: '/chat/c1', path: '/chat/:chatId' });
    act(() => useModalStore.getState().show('code-history'));
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  it('the admin can open the browser window', () => {
    signInAs(ADMIN);
    vi.spyOn(portalApi, 'init').mockResolvedValue({});
    renderWithProviders(<DialogHost />);
    act(() => useModalStore.getState().show('portal'));
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });
});
