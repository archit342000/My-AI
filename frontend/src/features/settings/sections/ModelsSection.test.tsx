import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, screen, waitFor } from '@testing-library/react';
import { ApiError } from '../../../api/client';
import { modelsApi } from '../../../api/settings';
import { useToastStore } from '../../../components/ui/toast-store';
import { renderWithProviders } from '../../../test/render';
import { ModelsSection } from './ModelsSection';

const models = [
  { id: 'A', status: { value: 'loaded' } },
  { id: 'B', status: { value: 'unloaded' } },
];
const toasts = () => useToastStore.getState().toasts.map((t) => t.message);

describe('ModelsSection', () => {
  beforeEach(() => useToastStore.setState({ toasts: [] }));
  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it('lists models with their state and offers Unload for a loaded one, Load for the others', async () => {
    vi.spyOn(modelsApi, 'list').mockResolvedValue(models);
    renderWithProviders(<ModelsSection />);
    expect(await screen.findByText('Loaded')).toBeTruthy();
    expect(screen.getByText('Not loaded')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Unload' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Load' })).toBeTruthy();
  });

  it('a model without a status says so and offers Load', async () => {
    vi.spyOn(modelsApi, 'list').mockResolvedValue([{ id: 'C' }] as never);
    renderWithProviders(<ModelsSection />);
    expect(await screen.findByText('Status unknown')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Load' })).toBeTruthy();
  });

  it('Load holds the whole screen until the model reports loaded, then says it is ready', async () => {
    const list = vi.spyOn(modelsApi, 'list').mockResolvedValue(models);
    const load = vi.spyOn(modelsApi, 'load').mockResolvedValue(new Response(null) as never);
    const { client } = renderWithProviders(<ModelsSection />);
    fireEvent.click(await screen.findByRole('button', { name: 'Load' }));
    const hold = await screen.findByRole('alertdialog', { name: 'Switching models' });
    expect(hold).toHaveTextContent('loading B');
    await waitFor(() => expect(load).toHaveBeenCalledWith('B'));
    list.mockResolvedValue([
      { id: 'A', status: { value: 'unloaded' } },
      { id: 'B', status: { value: 'loaded' } },
    ]);
    await client.invalidateQueries({ queryKey: ['models'] });
    await waitFor(() => expect(screen.queryByRole('alertdialog')).toBeNull());
    expect(toasts()).toContain('B is ready');
  });

  it('a load that fails ends the wait and says why', async () => {
    vi.spyOn(modelsApi, 'list').mockResolvedValue(models);
    vi.spyOn(modelsApi, 'load').mockRejectedValue(new ApiError(500, {}, 'out of memory'));
    renderWithProviders(<ModelsSection />);
    fireEvent.click(await screen.findByRole('button', { name: 'Load' }));
    await waitFor(() => expect(toasts()).toContain('out of memory'));
    expect(screen.queryByRole('alertdialog')).toBeNull();
  });

  it('the wait gives up after three minutes and says the load carries on', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.spyOn(modelsApi, 'list').mockResolvedValue(models);
    vi.spyOn(modelsApi, 'load').mockResolvedValue(new Response(null) as never);
    renderWithProviders(<ModelsSection />);
    fireEvent.click(await screen.findByRole('button', { name: 'Load' }));
    await screen.findByRole('alertdialog', { name: 'Switching models' });
    await act(() => vi.advanceTimersByTimeAsync(180_000));
    expect(screen.queryByRole('alertdialog')).toBeNull();
    expect(toasts().some((m) => m.startsWith('B is still loading'))).toBe(true);
  });

  it('Unload calls the API for the loaded model', async () => {
    vi.spyOn(modelsApi, 'list').mockResolvedValue(models);
    const unload = vi.spyOn(modelsApi, 'unload').mockResolvedValue(new Response(null) as never);
    renderWithProviders(<ModelsSection />);
    fireEvent.click(await screen.findByRole('button', { name: 'Unload' }));
    await waitFor(() => expect(unload).toHaveBeenCalledWith('A'));
  });

  it('search appears once the list is long, and narrows it', async () => {
    vi.spyOn(modelsApi, 'list').mockResolvedValue(
      ['alpha', 'beta', 'gamma', 'delta', 'epsilon', 'zeta'].map((id) => ({ id })) as never,
    );
    renderWithProviders(<ModelsSection />);
    fireEvent.change(await screen.findByLabelText('Search models'), { target: { value: 'ET' } });
    expect(screen.getByText('beta')).toBeTruthy();
    expect(screen.getByText('zeta')).toBeTruthy();
    expect(screen.queryByText('alpha')).toBeNull();
    fireEvent.change(screen.getByLabelText('Search models'), { target: { value: 'nothing' } });
    expect(screen.getByText('Nothing matches.')).toBeTruthy();
  });

  it('says so when the models cannot be listed', async () => {
    vi.spyOn(modelsApi, 'list').mockRejectedValue(new Error('down'));
    renderWithProviders(<ModelsSection />);
    expect(await screen.findByRole('alert')).toHaveTextContent('could not be listed');
  });

  it('holds the speed test, with Run off until a model is chosen', async () => {
    vi.spyOn(modelsApi, 'list').mockResolvedValue(models);
    renderWithProviders(<ModelsSection />);
    await screen.findByText('Loaded');
    expect(screen.getByRole('button', { name: 'Run' })).toBeDisabled();
    fireEvent.click(screen.getByRole('combobox', { name: 'Model to test' }));
    fireEvent.click(screen.getByRole('option', { name: /^A\b/ }));
    expect(screen.getByRole('button', { name: 'Run' })).toBeEnabled();
  });
});
