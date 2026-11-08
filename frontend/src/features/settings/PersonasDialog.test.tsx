import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { renderWithProviders } from '../../test/render';
import { PersonasDialog } from './PersonasDialog';
import { personasApi } from '../../api/settings';

const persona = { id: 'p1', name: 'Coach', content: 'Encourage the user', is_default: 1, research_mode: 0, file_system_mode: 0, browsing_mode: 0, git_mode: 0 };

describe('PersonasDialog', () => {
  afterEach(() => vi.restoreAllMocks());

  it('marks the default persona in its title and previews instructions', async () => {
    vi.spyOn(personasApi, 'list').mockResolvedValue([persona]);
    renderWithProviders(<PersonasDialog open onClose={() => undefined} />);
    expect(await screen.findByText('Coach (default)')).toBeTruthy();
    expect(screen.getByText('Encourage the user')).toBeTruthy();
  });

  it('requires a name and instructions', async () => {
    vi.spyOn(personasApi, 'list').mockResolvedValue([]);
    const create = vi.spyOn(personasApi, 'create');
    renderWithProviders(<PersonasDialog open onClose={() => undefined} />);
    fireEvent.click(await screen.findByRole('button', { name: /Add/ }));
    // Save stays disabled until the form is valid, so nothing can be submitted.
    expect((screen.getByRole('button', { name: 'Save' }) as HTMLButtonElement).disabled).toBe(true);
    expect(create).not.toHaveBeenCalled();
  });

  it('creates a persona with mode flags set by the toggles', async () => {
    vi.spyOn(personasApi, 'list').mockResolvedValue([]);
    const create = vi.spyOn(personasApi, 'create').mockResolvedValue(new Response(null) as never);
    renderWithProviders(<PersonasDialog open onClose={() => undefined} />);
    fireEvent.click(await screen.findByRole('button', { name: /Add/ }));
    fireEvent.change(screen.getByRole('textbox', { name: /Name/ }), { target: { value: 'Analyst' } });
    fireEvent.change(screen.getByRole('textbox', { name: /Instructions/ }), { target: { value: 'Be rigorous' } });
    fireEvent.click(screen.getByRole('switch', { name: 'Research mode' }));
    fireEvent.click(screen.getByRole('switch', { name: 'Git mode' }));
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() => expect(create).toHaveBeenCalled());
    expect(create.mock.calls[0]![0]).toMatchObject({ name: 'Analyst', content: 'Be rigorous', research_mode: 1, git_mode: 1, is_default: 0 });
  });

  it('a duplicate persona name shows the server message inline (N10)', async () => {
    vi.spyOn(personasApi, 'list').mockResolvedValue([]);
    vi.spyOn(personasApi, 'create').mockRejectedValue(new Error("A persona named 'Analyst' already exists."));
    renderWithProviders(<PersonasDialog open onClose={() => undefined} />);
    fireEvent.click(await screen.findByRole('button', { name: /Add/ }));
    fireEvent.change(screen.getByRole('textbox', { name: /Name/ }), { target: { value: 'Analyst' } });
    fireEvent.change(screen.getByRole('textbox', { name: /Instructions/ }), { target: { value: 'Be rigorous' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('already exists');
  });

  it('editing keeps existing flags and updates by id', async () => {
    vi.spyOn(personasApi, 'list').mockResolvedValue([persona]);
    const update = vi.spyOn(personasApi, 'update').mockResolvedValue(new Response(null) as never);
    renderWithProviders(<PersonasDialog open onClose={() => undefined} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Edit Coach (default)' }));
    expect((screen.getByRole('switch', { name: 'Default persona' }) as HTMLElement).getAttribute('aria-checked')).toBe('true');
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() => expect(update).toHaveBeenCalledWith('p1', expect.objectContaining({ name: 'Coach', is_default: 1 })));
  });

  it('deleting a persona calls the API after confirmation', async () => {
    vi.spyOn(personasApi, 'list').mockResolvedValue([persona]);
    const remove = vi.spyOn(personasApi, 'remove').mockResolvedValue(new Response(null) as never);
    renderWithProviders(<PersonasDialog open onClose={() => undefined} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Delete Coach (default)' }));
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }));
    await waitFor(() => expect(remove).toHaveBeenCalledWith('p1'));
  });
});
