import { act, fireEvent, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useUiStore } from '../../state/ui-store';
import { renderWithProviders } from '../../test/render';
import * as temporary from '../chat/temporary-chat';
import { TemporaryNote } from './TemporaryNote';

describe('TemporaryNote', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    act(() => useUiStore.getState().setTemporaryChatId(null));
  });

  it('shows nothing until a temporary chat is on', () => {
    renderWithProviders(<TemporaryNote />);
    expect(screen.queryByText(/Temporary chat/)).toBeNull();
  });

  it('says nothing is kept, and Save chat keeps it and opens the saved chat', async () => {
    const save = vi.spyOn(temporary, 'saveTemporaryChat').mockResolvedValue('c9');
    act(() => useUiStore.getState().setTemporaryChatId('t1'));
    renderWithProviders(<TemporaryNote />);
    expect(screen.getByText(/Nothing here is kept when you leave/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Save chat' }));
    await waitFor(() => expect(save).toHaveBeenCalledTimes(1));
    expect(await screen.findByTestId('elsewhere')).toBeTruthy();
  });

  it('is not shown on a saved chat', () => {
    act(() => useUiStore.getState().setTemporaryChatId('t1'));
    renderWithProviders(<TemporaryNote />, { route: '/chat/c1', path: '/chat/:chatId' });
    expect(screen.queryByText(/Temporary chat/)).toBeNull();
  });
});
