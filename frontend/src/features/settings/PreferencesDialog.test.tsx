import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { renderWithProviders } from '../../test/render';
import { PreferencesDialog } from './PreferencesDialog';
import { preferencesApi } from '../../api/settings';
import { useToastStore } from '../../components/ui/toast-store';

const prefs = [{ id: 'p1', content: 'Use metric units', tag: 'units', timestamp: 1 }];

describe('PreferencesDialog', () => {
  afterEach(() => vi.restoreAllMocks());

  it('lists saved preferences with their tag', async () => {
    vi.spyOn(preferencesApi, 'list').mockResolvedValue(prefs);
    renderWithProviders(<PreferencesDialog open onClose={() => undefined} />);
    expect(await screen.findByText('Use metric units')).toBeTruthy();
    expect(screen.getByText('Units')).toBeTruthy();
  });

  it('shows the empty-state copy when nothing is saved', async () => {
    vi.spyOn(preferencesApi, 'list').mockResolvedValue([]);
    renderWithProviders(<PreferencesDialog open onClose={() => undefined} />);
    expect(await screen.findByText(/Nothing saved yet/)).toBeTruthy();
  });

  it('adding a preference creates it with trimmed content and default tag', async () => {
    vi.spyOn(preferencesApi, 'list').mockResolvedValue([]);
    const create = vi.spyOn(preferencesApi, 'create').mockResolvedValue(new Response(null) as never);
    renderWithProviders(<PreferencesDialog open onClose={() => undefined} />);
    fireEvent.click(await screen.findByRole('button', { name: /Add/ }));
    fireEvent.change(screen.getByRole('textbox', { name: /Preference/ }), { target: { value: '  Be concise  ' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() => expect(create).toHaveBeenCalledWith({ content: 'Be concise', tag: 'preference' }));
  });

  it('a blank preference is not saved', async () => {
    vi.spyOn(preferencesApi, 'list').mockResolvedValue([]);
    const create = vi.spyOn(preferencesApi, 'create');
    renderWithProviders(<PreferencesDialog open onClose={() => undefined} />);
    fireEvent.click(await screen.findByRole('button', { name: /Add/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    await new Promise((r) => setTimeout(r, 20));
    expect(create).not.toHaveBeenCalled();
  });

  it('editing updates the existing preference', async () => {
    vi.spyOn(preferencesApi, 'list').mockResolvedValue(prefs);
    const update = vi.spyOn(preferencesApi, 'update').mockResolvedValue(new Response(null) as never);
    renderWithProviders(<PreferencesDialog open onClose={() => undefined} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Edit Use metric units' }));
    fireEvent.change(screen.getByRole('textbox', { name: /Tag/ }), { target: { value: 'style' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() => expect(update).toHaveBeenCalledWith('p1', { content: 'Use metric units', tag: 'style' }));
  });

  it('deleting removes the preference and confirms with a toast', async () => {
    vi.spyOn(preferencesApi, 'list').mockResolvedValue(prefs);
    const remove = vi.spyOn(preferencesApi, 'remove').mockResolvedValue(new Response(null) as never);
    renderWithProviders(<PreferencesDialog open onClose={() => undefined} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Delete Use metric units' }));
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }));
    await waitFor(() => expect(remove).toHaveBeenCalledWith('p1'));
    await waitFor(() => expect(useToastStore.getState().toasts.some((t) => t.message === 'Preference removed')).toBe(true));
  });

  it('a failed delete tells the user (N6)', async () => {
    vi.spyOn(preferencesApi, 'list').mockResolvedValue(prefs);
    vi.spyOn(preferencesApi, 'remove').mockRejectedValue(new Error('server 500'));
    renderWithProviders(<PreferencesDialog open onClose={() => undefined} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Delete Use metric units' }));
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }));
    await waitFor(() => expect(useToastStore.getState().toasts.some((t) => t.type === 'error')).toBe(true), { timeout: 500 });
  });
});

describe('PreferencesDialog search, filter and sort', () => {
  afterEach(() => vi.restoreAllMocks());
  const many = [
    { id: 'a', content: 'Answer in British English', tag: 'preference', timestamp: 100 },
    { id: 'b', content: 'The project is called Atlas', tag: 'project', timestamp: 300 },
    { id: 'c', content: 'Use metric units', tag: 'preference', timestamp: 200 },
  ];
  const rows = () => Array.from(document.querySelectorAll('.crud-row__title')).map((e) => e.textContent);

  it('typing in the search narrows the rows', async () => {
    vi.spyOn(preferencesApi, 'list').mockResolvedValue(many);
    renderWithProviders(<PreferencesDialog open onClose={() => undefined} />);
    await screen.findByText('Use metric units');
    fireEvent.change(screen.getByLabelText('Search memory'), { target: { value: 'atlas' } });
    expect(rows()).toEqual(['The project is called Atlas']);
  });

  it('the tag filter keeps one tag and the sort changes the order', async () => {
    vi.spyOn(preferencesApi, 'list').mockResolvedValue(many);
    renderWithProviders(<PreferencesDialog open onClose={() => undefined} />);
    await screen.findByText('Use metric units');
    expect(rows()).toEqual(['The project is called Atlas', 'Use metric units', 'Answer in British English']); // newest first
    fireEvent.click(screen.getByRole('combobox', { name: 'Sort' }));
    fireEvent.click(screen.getByRole('option', { name: 'Oldest' }));
    expect(rows()).toEqual(['Answer in British English', 'Use metric units', 'The project is called Atlas']);
    fireEvent.click(screen.getByRole('combobox', { name: 'Filter by tag' }));
    fireEvent.click(screen.getByRole('option', { name: 'Project' }));
    expect(rows()).toEqual(['The project is called Atlas']);
  });

  it('a query with no result says "No matches" and Add still works', async () => {
    vi.spyOn(preferencesApi, 'list').mockResolvedValue(many);
    renderWithProviders(<PreferencesDialog open onClose={() => undefined} />);
    await screen.findByText('Use metric units');
    fireEvent.change(screen.getByLabelText('Search memory'), { target: { value: 'zzz' } });
    expect(screen.getByText('No matches')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: /Add/ }));
    expect(screen.getByRole('heading', { name: 'New memory' })).toBeTruthy();
  });
});
