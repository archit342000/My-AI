import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, screen } from '@testing-library/react';
import { renderWithProviders } from '../../test/render';
import { ChatSettingsModal } from './ChatSettingsModal';
import { modelsApi, personasApi } from '../../api/settings';
import { useSettingsStore } from '../../state/settings-store';
import { useUserStore } from '../../state/user-store';
import { initUserStorage } from '../../lib/user-storage';

const ADMIN = { id: 'a1', email: 'a@x', role: 'admin' } as const;

describe('ChatSettingsModal', () => {
  beforeEach(() => {
    localStorage.clear();
    initUserStorage(ADMIN);
    useUserStore.setState({ user: ADMIN });
    useSettingsStore.getState().hydrate();
    vi.spyOn(modelsApi, 'list').mockResolvedValue([
      { id: 'm1', name: 'Model 1' },
      { id: 'm2', name: 'Model 2' },
    ] as never);
    vi.spyOn(personasApi, 'list').mockResolvedValue([] as never);
  });
  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it('shows "Model updated" after choosing a model and clears it after three seconds', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    renderWithProviders(<ChatSettingsModal open onClose={() => undefined} />);
    fireEvent.click(screen.getByRole('combobox', { name: 'Model' }));
    fireEvent.click(await screen.findByRole('option', { name: /m2/ }));
    expect(screen.getByRole('status')).toHaveTextContent('Model updated');
    expect(useSettingsStore.getState().model).toBe('m2');
    act(() => {
      vi.advanceTimersByTime(2999);
    });
    expect(screen.getByRole('status')).toBeTruthy();
    act(() => {
      vi.advanceTimersByTime(2);
    });
    expect(screen.queryByRole('status')).toBeNull();
  });

  it('choosing the same model again restarts the three seconds', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    renderWithProviders(<ChatSettingsModal open onClose={() => undefined} />);
    fireEvent.click(screen.getByRole('combobox', { name: 'Model' }));
    fireEvent.click(await screen.findByRole('option', { name: /m2/ }));
    act(() => {
      vi.advanceTimersByTime(2000);
    });
    fireEvent.click(screen.getByRole('combobox', { name: 'Model' }));
    fireEvent.click(screen.getByRole('option', { name: /m2/ }));
    act(() => {
      vi.advanceTimersByTime(2000);
    });
    expect(screen.getByRole('status')).toBeTruthy(); // 2s after the second pick, not 4s after the first
    act(() => {
      vi.advanceTimersByTime(1100);
    });
    expect(screen.queryByRole('status')).toBeNull();
  });

  it('choosing the thinking profile None turns thinking off in the store', () => {
    renderWithProviders(<ChatSettingsModal open onClose={() => undefined} />);
    fireEvent.click(screen.getByRole('combobox', { name: 'Thinking profile' }));
    fireEvent.click(screen.getByRole('option', { name: /None/ }));
    expect(useSettingsStore.getState().sampling.thinking_profile).toBe('none');
    expect(useSettingsStore.getState().sampling.enable_thinking).toBe(false);
  });
});
