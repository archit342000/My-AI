import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import { settingsApi } from '../../../api/settings';
import { useToastStore } from '../../../components/ui/toast-store';
import { resetSaveLight, useSaveLight } from '../../../lib/save-light';
import { renderWithProviders } from '../../../test/render';
import { AgentsSection } from './AgentsSection';

const agents = {
  research: { max_tokens: 4096, thinking_budget: 1000, thinking_profile: 'general' },
};
const tokens = async () =>
  (await screen.findByLabelText('Longest answer (tokens)')) as HTMLInputElement;

describe('AgentsSection', () => {
  beforeEach(() => {
    resetSaveLight();
    useToastStore.setState({ toasts: [] });
    vi.spyOn(settingsApi, 'getAgents').mockResolvedValue(agents as never);
    vi.spyOn(settingsApi, 'getBrowser').mockResolvedValue({ stealth_level: 'minimal' });
    vi.spyOn(settingsApi, 'getSystem').mockResolvedValue({
      github_pat_configured: true,
      git_known_commands: ['status'],
      git_allowed_commands: [],
    } as never);
  });
  afterEach(() => vi.restoreAllMocks());

  it('has no Save button: a number is kept when its box is left, and the light says Saved', async () => {
    const patch = vi
      .spyOn(settingsApi, 'patchAgent')
      .mockResolvedValue(new Response(null) as never);
    renderWithProviders(<AgentsSection />);
    const field = await tokens();
    expect(screen.queryByRole('button', { name: /Save changes/ })).toBeNull();
    fireEvent.focus(field);
    fireEvent.change(field, { target: { value: '8192' } });
    expect(patch).not.toHaveBeenCalled();
    fireEvent.blur(field);
    await waitFor(() =>
      expect(patch).toHaveBeenCalledWith('research', {
        max_tokens: 8192,
        thinking_budget: 1000,
        thinking_profile: 'general',
      }),
    );
    await waitFor(() => expect(useSaveLight.getState().state).toBe('saved'));
  });

  it('Enter keeps a number too, and leaving a box unchanged sends nothing', async () => {
    const patch = vi
      .spyOn(settingsApi, 'patchAgent')
      .mockResolvedValue(new Response(null) as never);
    renderWithProviders(<AgentsSection />);
    const field = await tokens();
    fireEvent.focus(field);
    fireEvent.blur(field);
    expect(patch).not.toHaveBeenCalled();
    const budget = screen.getByLabelText('Thinking budget (tokens)');
    fireEvent.focus(budget);
    fireEvent.change(budget, { target: { value: '0' } });
    fireEvent.keyDown(budget, { key: 'Enter' });
    await waitFor(() =>
      expect(patch).toHaveBeenCalledWith(
        'research',
        expect.objectContaining({ thinking_budget: 0 }),
      ),
    );
  });

  it('a number that is too small is refused where it is typed and not sent', async () => {
    const patch = vi
      .spyOn(settingsApi, 'patchAgent')
      .mockResolvedValue(new Response(null) as never);
    renderWithProviders(<AgentsSection />);
    const field = await tokens();
    fireEvent.focus(field);
    fireEvent.change(field, { target: { value: '10' } });
    fireEvent.blur(field);
    expect(screen.getByText('At least 256 tokens.')).toBeTruthy();
    expect(patch).not.toHaveBeenCalled();
  });

  it('the thinking profile is kept the moment it is chosen', async () => {
    const patch = vi
      .spyOn(settingsApi, 'patchAgent')
      .mockResolvedValue(new Response(null) as never);
    renderWithProviders(<AgentsSection />);
    await tokens();
    fireEvent.click(screen.getByRole('combobox', { name: /thinking profile$/ }));
    fireEvent.click(screen.getByRole('option', { name: /Precision/ }));
    await waitFor(() =>
      expect(patch).toHaveBeenCalledWith(
        'research',
        expect.objectContaining({ thinking_profile: 'precision', max_tokens: 4096 }),
      ),
    );
  });

  it('what is being typed survives a refresh from the server; an untouched box follows it', async () => {
    const get = vi.mocked(settingsApi.getAgents);
    const { client } = renderWithProviders(<AgentsSection />);
    const field = await tokens();
    fireEvent.focus(field);
    fireEvent.change(field, { target: { value: '9999' } });
    get.mockResolvedValue({
      research: { max_tokens: 2048, thinking_budget: 500, thinking_profile: 'general' },
    } as never);
    await client.invalidateQueries({ queryKey: ['settings', 'agents'] });
    await waitFor(() =>
      expect((screen.getByLabelText('Thinking budget (tokens)') as HTMLInputElement).value).toBe(
        '500',
      ),
    );
    expect(field.value).toBe('9999');
  });

  it('a save that fails puts the value back and says why', async () => {
    vi.spyOn(settingsApi, 'patchAgent').mockRejectedValue(new Error('not allowed'));
    renderWithProviders(<AgentsSection />);
    const field = await tokens();
    fireEvent.focus(field);
    fireEvent.change(field, { target: { value: '8192' } });
    fireEvent.blur(field);
    await waitFor(() =>
      expect(useToastStore.getState().toasts.some((t) => t.message === 'not allowed')).toBe(true),
    );
    await waitFor(async () => expect((await tokens()).value).toBe('4096'));
    expect(useSaveLight.getState().state).toBe('error');
  });

  it('browser stealth is one choice of two, kept at once', async () => {
    const set = vi.spyOn(settingsApi, 'setBrowser').mockResolvedValue(new Response(null) as never);
    renderWithProviders(<AgentsSection />);
    const group = await screen.findByRole('radiogroup', { name: 'Browser stealth' });
    await waitFor(() =>
      expect(
        within(group).getByRole('radio', { name: 'Minimal' }).getAttribute('aria-checked'),
      ).toBe('true'),
    );
    fireEvent.click(within(group).getByRole('radio', { name: 'Advanced' }));
    await waitFor(() => expect(set).toHaveBeenCalledWith('advanced'));
  });

  it('holds the git agent settings', async () => {
    renderWithProviders(<AgentsSection />);
    expect(await screen.findByLabelText('GitHub token')).toBeTruthy();
    expect(screen.getByRole('checkbox', { name: 'status' })).toBeTruthy();
  });
});
