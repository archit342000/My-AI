import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { renderWithProviders } from '../../test/render';
import { ModelsDialog } from './ModelsDialog';
import { modelsApi } from '../../api/settings';
import { ApiError } from '../../api/client';
import { useToastStore } from '../../components/ui/toast-store';

const models = [
  { id: 'A', status: { value: 'loaded' } },
  { id: 'B', status: { value: 'unloaded' } },
];

describe('ModelsDialog', () => {
  afterEach(() => vi.restoreAllMocks());

  it('lists instances with status and offers Unload for loaded, Load for others', async () => {
    vi.spyOn(modelsApi, 'list').mockResolvedValue(models);
    renderWithProviders(<ModelsDialog open onClose={() => undefined} />);
    expect((await screen.findAllByText('A')).length).toBeGreaterThan(0);
    expect(screen.getByRole('button', { name: 'Unload' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Load' })).toBeTruthy();
  });

  it('Load calls the API and queues a toast', async () => {
    vi.spyOn(modelsApi, 'list').mockResolvedValue(models);
    const load = vi.spyOn(modelsApi, 'load').mockResolvedValue(new Response(null) as never);
    renderWithProviders(<ModelsDialog open onClose={() => undefined} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Load' }));
    await waitFor(() => expect(load).toHaveBeenCalledWith('B'));
    expect(useToastStore.getState().toasts.some((t) => t.message === 'Loading B')).toBe(true);
  });

  it('Unload calls the API for the loaded model', async () => {
    vi.spyOn(modelsApi, 'list').mockResolvedValue(models);
    const unload = vi.spyOn(modelsApi, 'unload').mockResolvedValue(new Response(null) as never);
    renderWithProviders(<ModelsDialog open onClose={() => undefined} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Unload' }));
    await waitFor(() => expect(unload).toHaveBeenCalledWith('A'));
  });

  it('a failed load shows the error toast', async () => {
    vi.spyOn(modelsApi, 'list').mockResolvedValue(models);
    vi.spyOn(modelsApi, 'load').mockRejectedValue(new ApiError(500, {}, 'out of memory'));
    renderWithProviders(<ModelsDialog open onClose={() => undefined} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Load' }));
    await waitFor(() => expect(useToastStore.getState().toasts.some((t) => t.message === 'out of memory')).toBe(true));
  });

  it('shows the speed test and keeps Run disabled until a model is chosen', async () => {
    vi.spyOn(modelsApi, 'list').mockResolvedValue(models);
    renderWithProviders(<ModelsDialog open onClose={() => undefined} />);
    await screen.findAllByText('A');
    const run = screen.getByRole('button', { name: 'Run speed test' }) as HTMLButtonElement;
    expect(run.disabled).toBe(true);
    fireEvent.click(screen.getByRole('combobox', { name: 'Speed test target' }));
    fireEvent.click(screen.getByRole('option', { name: /^A\b/ }));
    expect(run.disabled).toBe(false);
  });

  it('an instance without a status object shows "Status unknown" and offers Load (F8)', async () => {
    vi.spyOn(modelsApi, 'list').mockResolvedValue([{ id: 'C' }] as never);
    renderWithProviders(<ModelsDialog open onClose={() => undefined} />);
    expect(await screen.findByText('Status unknown')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Load' })).toBeTruthy();
  });
});
