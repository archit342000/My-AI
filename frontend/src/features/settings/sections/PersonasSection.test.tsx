import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { renderWithProviders } from '../../../test/render';
import { PersonasSection } from './PersonasSection';
import { personasApi } from '../../../api/settings';

const persona = { id: 'p1', name: 'Coach', content: 'Encourage the user', is_default: 1, research_mode: 0, file_system_mode: 0, browsing_mode: 0, git_mode: 0 };

describe('PersonasSection', () => {
  afterEach(() => vi.restoreAllMocks());

  it('marks the default persona and previews its instructions', async () => {
    vi.spyOn(personasApi, 'list').mockResolvedValue([persona]);
    renderWithProviders(<PersonasSection />);
    expect(await screen.findByText('Coach')).toBeTruthy();
    expect(screen.getByText('Default')).toBeTruthy();
    expect(screen.getByText('Encourage the user')).toBeTruthy();
  });

  it('requires a name and instructions', async () => {
    vi.spyOn(personasApi, 'list').mockResolvedValue([]);
    const create = vi.spyOn(personasApi, 'create');
    renderWithProviders(<PersonasSection />);
    fireEvent.click(await screen.findByRole('button', { name: 'New persona' }));
    // Save stays disabled until the form is valid, so nothing can be submitted.
    expect((screen.getByRole('button', { name: 'Save' }) as HTMLButtonElement).disabled).toBe(true);
    expect(create).not.toHaveBeenCalled();
  });

  it('creates a persona with mode flags set by the toggles', async () => {
    vi.spyOn(personasApi, 'list').mockResolvedValue([]);
    const create = vi.spyOn(personasApi, 'create').mockResolvedValue(new Response(null) as never);
    renderWithProviders(<PersonasSection />);
    fireEvent.click(await screen.findByRole('button', { name: 'New persona' }));
    fireEvent.change(screen.getByRole('textbox', { name: /Name/ }), { target: { value: 'Analyst' } });
    fireEvent.change(screen.getByRole('textbox', { name: /Instructions/ }), { target: { value: 'Be rigorous' } });
    fireEvent.click(screen.getByRole('switch', { name: 'Research mode' }));
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() => expect(create).toHaveBeenCalled());
    expect(create.mock.calls[0]?.[0]).toMatchObject({ name: 'Analyst', content: 'Be rigorous', research_mode: 1, is_default: 0 });
    const body: unknown = create.mock.calls[0]?.[0];
    expect(body).not.toHaveProperty('git_mode');
  });

  it('editing sends only the fields the server stores, even if the row carries more', async () => {
    vi.spyOn(personasApi, 'list').mockResolvedValue([{ ...persona, git_mode: 1, extra_runtime_field: 'x' } as never]);
    const update = vi.spyOn(personasApi, 'update').mockResolvedValue(new Response(null) as never);
    renderWithProviders(<PersonasSection />);
    fireEvent.click(await screen.findByRole('button', { name: 'Edit Coach' }));
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() => expect(update).toHaveBeenCalled());
    const body = update.mock.calls[0]?.[1] as Record<string, unknown>;
    expect(Object.keys(body).sort()).toEqual(['browsing_mode', 'content', 'file_system_mode', 'is_default', 'name', 'research_mode']);
  });

  it('offers only the flags the server stores', async () => {
    vi.spyOn(personasApi, 'list').mockResolvedValue([]);
    renderWithProviders(<PersonasSection />);
    fireEvent.click(await screen.findByRole('button', { name: 'New persona' }));
    expect(screen.queryByRole('switch', { name: 'Git mode' })).toBeNull();
    expect(screen.queryByRole('switch', { name: /Code execution/i })).toBeNull();
    for (const name of ['Default persona', 'Research mode', 'File system mode', 'Browsing mode']) {
      expect(screen.getByRole('switch', { name })).toBeTruthy();
    }
  });

  it('a duplicate persona name shows the server message inline (N10)', async () => {
    vi.spyOn(personasApi, 'list').mockResolvedValue([]);
    vi.spyOn(personasApi, 'create').mockRejectedValue(new Error("A persona named 'Analyst' already exists."));
    renderWithProviders(<PersonasSection />);
    fireEvent.click(await screen.findByRole('button', { name: 'New persona' }));
    fireEvent.change(screen.getByRole('textbox', { name: /Name/ }), { target: { value: 'Analyst' } });
    fireEvent.change(screen.getByRole('textbox', { name: /Instructions/ }), { target: { value: 'Be rigorous' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('already exists');
  });

  it('editing keeps existing flags and updates by id', async () => {
    vi.spyOn(personasApi, 'list').mockResolvedValue([persona]);
    const update = vi.spyOn(personasApi, 'update').mockResolvedValue(new Response(null) as never);
    renderWithProviders(<PersonasSection />);
    fireEvent.click(await screen.findByRole('button', { name: 'Edit Coach' }));
    expect((screen.getByRole('switch', { name: 'Default persona' }) as HTMLElement).getAttribute('aria-checked')).toBe('true');
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() => expect(update).toHaveBeenCalledWith('p1', expect.objectContaining({ name: 'Coach', is_default: 1 })));
  });

  it('deleting a persona calls the API after confirmation', async () => {
    vi.spyOn(personasApi, 'list').mockResolvedValue([persona]);
    const remove = vi.spyOn(personasApi, 'remove').mockResolvedValue(new Response(null) as never);
    renderWithProviders(<PersonasSection />);
    fireEvent.click(await screen.findByRole('button', { name: 'Delete Coach' }));
    fireEvent.click(screen.getByRole('button', { name: 'Delete persona' }));
    await waitFor(() => expect(remove).toHaveBeenCalledWith('p1'));
  });
});
