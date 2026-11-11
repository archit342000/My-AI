import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { useQuery } from '@tanstack/react-query';
import { settingsApi, settingsKeys } from '../../api/settings';
import { useToastStore } from '../../components/ui/toast-store';
import { renderWithProviders } from '../../test/render';
import { GitSettings } from './GitSettingsSection';

const system = {
  code_runner_timeout: 30,
  code_runner_memory_limit: '512M',
  code_runner_cpu_limit: '1.0',
  code_runner_max_output_size: 65536,
};

/** The settings as the Agents section gives them: read from the server, refreshed after a save. */
function Host() {
  const query = useQuery({ queryKey: settingsKeys.system, queryFn: settingsApi.getSystem });
  return query.data ? <GitSettings system={query.data} /> : null;
}

describe('GitSettings', () => {
  afterEach(() => vi.restoreAllMocks());
  const gitSystem = {
    ...system,
    github_pat_configured: false,
    git_known_commands: ['status', 'diff', 'commit'],
    git_allowed_commands: ['status'],
  };
  /** A server that remembers what was saved, as the real one does. */
  function mockSavingServer(failOn?: string) {
    let saved = gitSystem.git_allowed_commands;
    vi.spyOn(settingsApi, 'getSystem').mockImplementation(async () => ({
      ...gitSystem,
      git_allowed_commands: saved,
    }));
    return vi
      .spyOn(settingsApi, 'saveGitAllowedCommands')
      .mockImplementation(async (commands: string[]) => {
        if (failOn && commands.includes(failOn)) throw new Error('nope');
        saved = commands;
        return new Response(null);
      });
  }

  it('the admin sees the section with the token status and the allowed commands', async () => {
    vi.spyOn(settingsApi, 'getSystem').mockResolvedValue(gitSystem);
    renderWithProviders(<Host />);
    expect(await screen.findByText(/^None set\./)).toBeTruthy();
    expect(
      (screen.getByRole('checkbox', { name: 'status' }) as HTMLElement).getAttribute(
        'aria-checked',
      ),
    ).toBe('true');
    expect(
      (screen.getByRole('checkbox', { name: 'diff' }) as HTMLElement).getAttribute('aria-checked'),
    ).toBe('false');
  });

  it('saving a token posts it once, empties the field and reports it saved', async () => {
    vi.spyOn(settingsApi, 'getSystem').mockResolvedValue(gitSystem);
    const save = vi.spyOn(settingsApi, 'saveGitToken').mockResolvedValue(new Response(null));
    renderWithProviders(<Host />);
    const field = (await screen.findByLabelText('GitHub token')) as HTMLInputElement;
    expect(field.type).toBe('password');
    fireEvent.change(field, { target: { value: ' ghp_abc ' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save token' }));
    await waitFor(() => expect(save).toHaveBeenCalledWith('ghp_abc'));
    await waitFor(() => expect(field.value).toBe(''));
    expect(screen.getByText('Token saved')).toBeTruthy();
    expect(save).toHaveBeenCalledTimes(1);
  });

  it('ticking a command posts the full allowed list', async () => {
    const save = mockSavingServer();
    renderWithProviders(<Host />);
    fireEvent.click(await screen.findByRole('checkbox', { name: 'diff' }));
    await waitFor(() => expect(save).toHaveBeenCalledWith(['status', 'diff']));
    await waitFor(() =>
      expect((screen.getByRole('checkbox', { name: 'status' }) as HTMLButtonElement).disabled).toBe(
        false,
      ),
    );
    fireEvent.click(screen.getByRole('checkbox', { name: 'status' }));
    await waitFor(() => expect(save).toHaveBeenLastCalledWith(['diff']));
  });

  it('a failed save puts the checkbox back and says so', async () => {
    vi.spyOn(settingsApi, 'getSystem').mockResolvedValue(gitSystem);
    vi.spyOn(settingsApi, 'saveGitAllowedCommands').mockRejectedValue(new Error('nope'));
    renderWithProviders(<Host />);
    const box = await screen.findByRole('checkbox', { name: 'commit' });
    fireEvent.click(box);
    expect(box.getAttribute('aria-checked')).toBe('true'); // shown at once
    await waitFor(() => expect(box.getAttribute('aria-checked')).toBe('false'));
    expect(useToastStore.getState().toasts.some((t) => t.message === 'nope')).toBe(true);
  });

  it('the command boxes are locked while a save is in flight', async () => {
    vi.spyOn(settingsApi, 'getSystem').mockResolvedValue(gitSystem);
    let release: () => void = () => undefined;
    vi.spyOn(settingsApi, 'saveGitAllowedCommands').mockImplementation(
      () => new Promise<Response>((resolve) => (release = () => resolve(new Response(null)))),
    );
    renderWithProviders(<Host />);
    fireEvent.click(await screen.findByRole('checkbox', { name: 'diff' }));
    await waitFor(() =>
      expect((screen.getByRole('checkbox', { name: 'commit' }) as HTMLButtonElement).disabled).toBe(
        true,
      ),
    );
    release();
    await waitFor(() =>
      expect((screen.getByRole('checkbox', { name: 'commit' }) as HTMLButtonElement).disabled).toBe(
        false,
      ),
    );
  });

  it('a failed token save says why and keeps what was typed', async () => {
    vi.spyOn(settingsApi, 'getSystem').mockResolvedValue(gitSystem);
    vi.spyOn(settingsApi, 'saveGitToken').mockRejectedValue(new Error('bad token'));
    renderWithProviders(<Host />);
    const field = (await screen.findByLabelText('GitHub token')) as HTMLInputElement;
    fireEvent.change(field, { target: { value: 'ghp_abc' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save token' }));
    expect(await screen.findByText('bad token')).toBeTruthy();
    expect(field.value).toBe('ghp_abc');
  });

  it('a failed save goes back to the last saved list, not to the one the page loaded with', async () => {
    const save = mockSavingServer('commit');
    renderWithProviders(<Host />);
    const diff = await screen.findByRole('checkbox', { name: 'diff' });
    const commit = screen.getByRole('checkbox', { name: 'commit' });
    fireEvent.click(diff);
    await waitFor(() => expect(save).toHaveBeenCalledTimes(1));
    fireEvent.click(commit);
    await waitFor(() => expect(commit.getAttribute('aria-checked')).toBe('false'));
    expect(diff.getAttribute('aria-checked')).toBe('true');
  });
});
