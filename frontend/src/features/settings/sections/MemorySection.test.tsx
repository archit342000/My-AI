import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import { renderWithProviders } from '../../../test/render';
import { MemorySection } from './MemorySection';
import { preferencesApi } from '../../../api/settings';
import { useToastStore } from '../../../components/ui/toast-store';

const prefs = [{ id: 'p1', content: 'Use metric units', tag: 'units', timestamp: 1 }];

describe('MemorySection', () => {
  afterEach(() => vi.restoreAllMocks());

  it('lists saved preferences with their tag', async () => {
    vi.spyOn(preferencesApi, 'list').mockResolvedValue(prefs);
    renderWithProviders(<MemorySection />);
    expect(await screen.findByText('Use metric units')).toBeTruthy();
    expect(screen.getByText('Units')).toBeTruthy();
  });

  it('shows the empty-state copy when nothing is saved', async () => {
    vi.spyOn(preferencesApi, 'list').mockResolvedValue([]);
    renderWithProviders(<MemorySection />);
    expect(await screen.findByText(/Nothing saved yet/)).toBeTruthy();
  });

  it('adding a preference creates it with trimmed content and default tag', async () => {
    vi.spyOn(preferencesApi, 'list').mockResolvedValue([]);
    const create = vi.spyOn(preferencesApi, 'create').mockResolvedValue(new Response(null) as never);
    renderWithProviders(<MemorySection />);
    fireEvent.click(await screen.findByRole('button', { name: 'New preference' }));
    fireEvent.change(screen.getByRole('textbox', { name: /Preference/ }), { target: { value: '  Be concise  ' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() => expect(create).toHaveBeenCalledWith({ content: 'Be concise', tag: 'preference' }));
  });

  it('a blank preference is not saved', async () => {
    vi.spyOn(preferencesApi, 'list').mockResolvedValue([]);
    const create = vi.spyOn(preferencesApi, 'create');
    renderWithProviders(<MemorySection />);
    fireEvent.click(await screen.findByRole('button', { name: 'New preference' }));
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    await new Promise((r) => setTimeout(r, 20));
    expect(create).not.toHaveBeenCalled();
  });

  it('editing updates the existing preference', async () => {
    vi.spyOn(preferencesApi, 'list').mockResolvedValue(prefs);
    const update = vi.spyOn(preferencesApi, 'update').mockResolvedValue(new Response(null) as never);
    renderWithProviders(<MemorySection />);
    fireEvent.click(await screen.findByRole('button', { name: 'Edit Use metric units' }));
    fireEvent.change(screen.getByRole('textbox', { name: /Tag/ }), { target: { value: 'style' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() => expect(update).toHaveBeenCalledWith('p1', { content: 'Use metric units', tag: 'style' }));
  });

  it('deleting removes the preference after a confirmation', async () => {
    vi.spyOn(preferencesApi, 'list').mockResolvedValue(prefs);
    const remove = vi.spyOn(preferencesApi, 'remove').mockResolvedValue(new Response(null) as never);
    renderWithProviders(<MemorySection />);
    fireEvent.click(await screen.findByRole('button', { name: 'Delete Use metric units' }));
    fireEvent.click(screen.getByRole('button', { name: 'Delete preference' }));
    await waitFor(() => expect(remove).toHaveBeenCalledWith('p1'));
  });

  it('a failed delete tells the user (N6)', async () => {
    vi.spyOn(preferencesApi, 'list').mockResolvedValue(prefs);
    vi.spyOn(preferencesApi, 'remove').mockRejectedValue(new Error('server 500'));
    renderWithProviders(<MemorySection />);
    fireEvent.click(await screen.findByRole('button', { name: 'Delete Use metric units' }));
    fireEvent.click(screen.getByRole('button', { name: 'Delete preference' }));
    await waitFor(() => expect(useToastStore.getState().toasts.some((t) => t.type === 'error')).toBe(true), { timeout: 500 });
  });
});

describe('MemorySection search, filter and sort', () => {
  afterEach(() => vi.restoreAllMocks());
  const many = [
    { id: 'a', content: 'Answer in British English', tag: 'preference', timestamp: 100 },
    { id: 'b', content: 'The project is called Atlas', tag: 'project', timestamp: 300 },
    { id: 'c', content: 'Use metric units', tag: 'preference', timestamp: 200 },
  ];
  const rows = () => Array.from(document.querySelectorAll('.crud-title__name')).map((e) => e.textContent);

  it('typing in the search narrows the rows', async () => {
    vi.spyOn(preferencesApi, 'list').mockResolvedValue(many);
    renderWithProviders(<MemorySection />);
    await screen.findByText('Use metric units');
    fireEvent.change(screen.getByLabelText('Search memory'), { target: { value: 'atlas' } });
    expect(rows()).toEqual(['The project is called Atlas']);
  });

  it('the tag filter keeps one tag and the sort changes the order', async () => {
    vi.spyOn(preferencesApi, 'list').mockResolvedValue(many);
    renderWithProviders(<MemorySection />);
    await screen.findByText('Use metric units');
    expect(rows()).toEqual(['The project is called Atlas', 'Use metric units', 'Answer in British English']); // newest first
    fireEvent.click(screen.getByRole('combobox', { name: 'Order' }));
    fireEvent.click(screen.getByRole('option', { name: 'Oldest first' }));
    expect(rows()).toEqual(['Answer in British English', 'Use metric units', 'The project is called Atlas']);
    fireEvent.click(screen.getByRole('combobox', { name: 'Filter by tag' }));
    fireEvent.click(screen.getByRole('option', { name: 'Project' }));
    expect(rows()).toEqual(['The project is called Atlas']);
  });

  it('a query with no result says so and a new one can still be added', async () => {
    vi.spyOn(preferencesApi, 'list').mockResolvedValue(many);
    renderWithProviders(<MemorySection />);
    await screen.findByText('Use metric units');
    fireEvent.change(screen.getByLabelText('Search memory'), { target: { value: 'zzz' } });
    expect(screen.getByText('Nothing matches.')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'New preference' }));
    expect(screen.getByRole('group', { name: 'New preference' })).toBeTruthy();
  });

  it('Reset memory confirms, then forgets everything', async () => {
    vi.spyOn(preferencesApi, 'list').mockResolvedValue(many);
    const reset = vi.spyOn(preferencesApi, 'reset').mockResolvedValue(new Response(null) as never);
    renderWithProviders(<MemorySection />);
    await screen.findByText('Use metric units');
    fireEvent.click(screen.getByRole('button', { name: 'Reset memory' }));
    expect(reset).not.toHaveBeenCalled();
    fireEvent.click(
      within(screen.getByRole('dialog', { name: 'Reset memory?' })).getByRole('button', {
        name: 'Reset memory',
      }),
    );
    await waitFor(() => expect(reset).toHaveBeenCalled());
    await waitFor(() =>
      expect(useToastStore.getState().toasts.some((t) => t.message === 'Memory reset')).toBe(true),
    );
  });

  it('a reset that fails says why', async () => {
    vi.spyOn(preferencesApi, 'list').mockResolvedValue(many);
    vi.spyOn(preferencesApi, 'reset').mockRejectedValue(new Error('not now'));
    renderWithProviders(<MemorySection />);
    await screen.findByText('Use metric units');
    fireEvent.click(screen.getByRole('button', { name: 'Reset memory' }));
    fireEvent.click(
      within(screen.getByRole('dialog', { name: 'Reset memory?' })).getByRole('button', {
        name: 'Reset memory',
      }),
    );
    await waitFor(() =>
      expect(useToastStore.getState().toasts.some((t) => t.message === 'not now')).toBe(true),
    );
  });
});
