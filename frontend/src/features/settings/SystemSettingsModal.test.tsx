import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { renderWithProviders } from '../../test/render';
import { SystemSettingsModal } from './SystemSettingsModal';
import { settingsApi } from '../../api/settings';
import { ADMIN, USER, signInAs } from '../../test/roles';
import { chatsApi } from '../../api/chats';
import * as sendTurnModule from '../chat/send-turn';
import * as temporaryChatModule from '../chat/temporary-chat';
import { useStreamStore } from '../../state/stream-store';
import { useSettingsStore } from '../../state/settings-store';
import { useToastStore } from '../../components/ui/toast-store';

const system = {
  code_runner_timeout: 30,
  code_runner_memory_limit: '512M',
  code_runner_cpu_limit: '1.0',
  code_runner_max_output_size: 65536,
};

function mockSystem(extra: Record<string, unknown> = {}) {
  vi.spyOn(settingsApi, 'getSystem').mockResolvedValue({ ...system, ...extra });
  vi.spyOn(settingsApi, 'version').mockResolvedValue({ version: '1.0.0' });
}

describe('SystemSettingsModal code runner timeout', () => {
  afterEach(() => vi.restoreAllMocks());

  it('caps the timeout input at the maximum the API reports', async () => {
    mockSystem({ code_runner_max_timeout: 120 });
    renderWithProviders(<SystemSettingsModal open onClose={() => undefined} />);
    const input = (await screen.findByLabelText('Timeout (seconds)')) as HTMLInputElement;
    expect(input.max).toBe('120');
    expect(input.min).toBe('1');
  });

  it('has no max attribute when the API does not report one', async () => {
    mockSystem();
    renderWithProviders(<SystemSettingsModal open onClose={() => undefined} />);
    const input = (await screen.findByLabelText('Timeout (seconds)')) as HTMLInputElement;
    expect(input.getAttribute('max')).toBeNull();
  });

  it('does not send the read-only maximum back when saving', async () => {
    mockSystem({ code_runner_max_timeout: 120 });
    const save = vi.spyOn(settingsApi, 'saveCodeRunner').mockResolvedValue(new Response(null) as never);
    renderWithProviders(<SystemSettingsModal open onClose={() => undefined} />);
    await screen.findByLabelText('Timeout (seconds)');
    fireEvent.click(screen.getByRole('button', { name: 'Save code runner settings' }));
    await waitFor(() => expect(save).toHaveBeenCalled());
    const body = save.mock.calls[0]?.[0];
    expect(body).toEqual(system);
    expect(Object.keys(body ?? {})).not.toContain('code_runner_max_timeout');
  });
});

describe('SystemSettingsModal code runner form', () => {
  afterEach(() => vi.restoreAllMocks());

  it('uses the shared input and button styles and has no inline styles', async () => {
    mockSystem({ code_runner_max_timeout: 120 });
    renderWithProviders(<SystemSettingsModal open onClose={() => undefined} />);
    for (const label of ['Timeout (seconds)', 'Memory limit', 'CPU limit (cores)', 'Max output (bytes)']) {
      expect((await screen.findByLabelText(label)).className).toContain('ui-input');
    }
    const save = screen.getByRole('button', { name: 'Save code runner settings' });
    expect(save.className).toContain('ui-button');
    // nothing inside the dialog is styled inline, except the sliders' own fill variable (dynamic-style)
    expect(document.querySelectorAll('.modal-content [style]:not(.ui-slider__input)').length).toBe(0);
  });
});

describe('SystemSettingsModal by role', () => {
  afterEach(() => vi.restoreAllMocks());

  it('a user sees no runner settings and no admin links, and the system settings are never fetched', async () => {
    signInAs(USER);
    const getSystem = vi.spyOn(settingsApi, 'getSystem').mockResolvedValue({ ...system });
    vi.spyOn(settingsApi, 'version').mockResolvedValue({ version: '1.0.0' });
    renderWithProviders(<SystemSettingsModal open onClose={() => undefined} />);
    expect(await screen.findByText('Version 1.0.0')).toBeInTheDocument();
    expect(screen.queryByText('Code runner')).toBeNull();
    expect(screen.queryByLabelText('Timeout (seconds)')).toBeNull();
    for (const name of ['Agent configuration', 'Model manager', 'Browser stealth']) {
      expect(screen.queryByRole('button', { name })).toBeNull();
    }
    for (const name of ['Memory & preferences', 'Skills', 'Personas', 'Reset preferences']) {
      expect(screen.getByRole('button', { name })).toBeInTheDocument();
    }
    expect(getSystem).not.toHaveBeenCalled();
  });

  it('the admin sees the runner settings and every link', async () => {
    signInAs(ADMIN);
    vi.spyOn(settingsApi, 'getSystem').mockResolvedValue({ ...system });
    vi.spyOn(settingsApi, 'version').mockResolvedValue({ version: '1.0.0' });
    renderWithProviders(<SystemSettingsModal open onClose={() => undefined} />);
    expect(await screen.findByLabelText('Timeout (seconds)')).toBeInTheDocument();
    for (const name of ['Agent configuration', 'Model manager', 'Browser stealth', 'Skills']) {
      expect(screen.getByRole('button', { name })).toBeInTheDocument();
    }
  });
});

describe('SystemSettingsModal delete all chats', () => {
  beforeEach(() => {
    vi.spyOn(chatsApi, 'list').mockResolvedValue([]); // no chat is running unless a test says so
  });

  afterEach(() => {
    vi.restoreAllMocks();
    useStreamStore.setState({ chatId: null, live: null, pending: null, interrupted: null, controller: null });
  });

  it('asks first, then deletes everything, refreshes the lists, closes and goes to the empty home page', async () => {
    signInAs(USER);
    vi.spyOn(settingsApi, 'version').mockResolvedValue({ version: '1.0.0' });
    const bulk = vi.spyOn(chatsApi, 'bulkDelete').mockResolvedValue(new Response(null));
    const onClose = vi.fn();
    const { client } = renderWithProviders(<SystemSettingsModal open onClose={onClose} />, { route: '/chat/c1', path: '/chat/:chatId' });
    const invalidate = vi.spyOn(client, 'invalidateQueries');
    fireEvent.click(await screen.findByRole('button', { name: 'Delete all chats' }));
    expect(bulk).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Delete all' }));
    await waitFor(() => expect(bulk).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['chats'] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['workspaces'] });
    expect(await screen.findByTestId('elsewhere')).toBeTruthy(); // navigated away from /chat/:id
  });

  it('cancelling the confirmation deletes nothing', async () => {
    signInAs(USER);
    vi.spyOn(settingsApi, 'version').mockResolvedValue({ version: '1.0.0' });
    const bulk = vi.spyOn(chatsApi, 'bulkDelete').mockResolvedValue(new Response(null));
    renderWithProviders(<SystemSettingsModal open onClose={() => undefined} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Delete all chats' }));
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(bulk).not.toHaveBeenCalled();
  });

  it('stops the turn that is generating before it deletes', async () => {
    signInAs(USER);
    vi.spyOn(settingsApi, 'version').mockResolvedValue({ version: '1.0.0' });
    const order: string[] = [];
    useStreamStore.setState({ chatId: 'c1', controller: new AbortController() });
    vi.spyOn(sendTurnModule, 'stopIfStreaming').mockImplementation(async () => {
      order.push('stop');
    });
    vi.spyOn(chatsApi, 'bulkDelete').mockImplementation(async () => {
      order.push('delete');
      return new Response(null);
    });
    renderWithProviders(<SystemSettingsModal open onClose={() => undefined} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Delete all chats' }));
    fireEvent.click(screen.getByRole('button', { name: 'Delete all' }));
    await waitFor(() => expect(order).toEqual(['stop', 'delete']));
  });

  it('stops every chat the server reports as running, including one this tab does not hold, before it deletes', async () => {
    signInAs(USER);
    vi.spyOn(settingsApi, 'version').mockResolvedValue({ version: '1.0.0' });
    const order: string[] = [];
    vi.spyOn(chatsApi, 'list')
      .mockResolvedValueOnce([
        { id: 'other-tab', is_running: true },
        { id: 'idle', is_running: false },
      ] as never)
      .mockResolvedValue([{ id: 'other-tab', is_running: false }] as never); // stopped by the time it is checked again
    const stop = vi.spyOn(sendTurnModule, 'stopIfStreaming').mockImplementation(async (id: string) => {
      order.push(`stop ${id}`);
    });
    vi.spyOn(chatsApi, 'bulkDelete').mockImplementation(async () => {
      order.push('delete');
      return new Response(null);
    });
    renderWithProviders(<SystemSettingsModal open onClose={() => undefined} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Delete all chats' }));
    fireEvent.click(screen.getByRole('button', { name: 'Delete all' }));
    await waitFor(() => expect(order).toEqual(['stop other-tab', 'delete']));
    expect(stop).toHaveBeenCalledWith('other-tab', true);
  });

  it('when only the clean-up after the deletion fails, the chats are reported deleted and the page still leaves', async () => {
    signInAs(USER);
    vi.spyOn(settingsApi, 'version').mockResolvedValue({ version: '1.0.0' });
    vi.spyOn(chatsApi, 'bulkDelete').mockResolvedValue(new Response(null));
    vi.spyOn(temporaryChatModule, 'discardTemporaryChat').mockRejectedValue(new Error('late failure'));
    const onClose = vi.fn();
    renderWithProviders(<SystemSettingsModal open onClose={onClose} />, { route: '/chat/c1', path: '/chat/:chatId' });
    fireEvent.click(await screen.findByRole('button', { name: 'Delete all chats' }));
    fireEvent.click(screen.getByRole('button', { name: 'Delete all' }));
    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(useToastStore.getState().toasts.some((t) => t.message === 'All chats deleted')).toBe(true);
    expect(useToastStore.getState().toasts.some((t) => t.message.includes('could not be refreshed'))).toBe(true);
    expect(await screen.findByTestId('elsewhere')).toBeTruthy();
  });

  it('does not delete while a stop was refused and the chat is still running', async () => {
    signInAs(USER);
    vi.spyOn(settingsApi, 'version').mockResolvedValue({ version: '1.0.0' });
    vi.spyOn(chatsApi, 'list').mockResolvedValue([{ id: 'busy', is_running: true }] as never);
    vi.spyOn(sendTurnModule, 'stopIfStreaming').mockResolvedValue(undefined); // refused: it only toasts
    const bulk = vi.spyOn(chatsApi, 'bulkDelete').mockResolvedValue(new Response(null));
    const onClose = vi.fn();
    renderWithProviders(<SystemSettingsModal open onClose={onClose} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Delete all chats' }));
    fireEvent.click(screen.getByRole('button', { name: 'Delete all' }));
    await waitFor(() => expect(useToastStore.getState().toasts.some((t) => t.message.includes('still generating'))).toBe(true));
    expect(bulk).not.toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();
  });

  it('does not delete when the chat list cannot be read', async () => {
    signInAs(USER);
    vi.spyOn(settingsApi, 'version').mockResolvedValue({ version: '1.0.0' });
    vi.spyOn(chatsApi, 'list').mockRejectedValue(new Error('list down'));
    const bulk = vi.spyOn(chatsApi, 'bulkDelete').mockResolvedValue(new Response(null));
    renderWithProviders(<SystemSettingsModal open onClose={() => undefined} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Delete all chats' }));
    fireEvent.click(screen.getByRole('button', { name: 'Delete all' }));
    await waitFor(() => expect(useToastStore.getState().toasts.some((t) => t.message === 'list down')).toBe(true));
    expect(bulk).not.toHaveBeenCalled();
  });

  it('says why when the deletion fails and stays open', async () => {
    signInAs(USER);
    vi.spyOn(settingsApi, 'version').mockResolvedValue({ version: '1.0.0' });
    vi.spyOn(chatsApi, 'bulkDelete').mockRejectedValue(new Error('server busy'));
    const onClose = vi.fn();
    renderWithProviders(<SystemSettingsModal open onClose={onClose} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Delete all chats' }));
    fireEvent.click(screen.getByRole('button', { name: 'Delete all' }));
    await waitFor(() => expect(useToastStore.getState().toasts.some((t) => t.message === 'server busy')).toBe(true));
    expect(onClose).not.toHaveBeenCalled();
  });
});

describe('SystemSettingsModal git and defaults sections', () => {
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
    vi.spyOn(settingsApi, 'getSystem').mockImplementation(async () => ({ ...gitSystem, git_allowed_commands: saved }));
    return vi.spyOn(settingsApi, 'saveGitAllowedCommands').mockImplementation(async (commands: string[]) => {
      if (failOn && commands.includes(failOn)) throw new Error('nope');
      saved = commands;
      return new Response(null);
    });
  }

  it('a user sees no Git agent section', async () => {
    signInAs(USER);
    vi.spyOn(settingsApi, 'version').mockResolvedValue({ version: '1.0.0' });
    vi.spyOn(settingsApi, 'getSystem').mockResolvedValue(gitSystem);
    renderWithProviders(<SystemSettingsModal open onClose={() => undefined} />);
    await screen.findByText('Version 1.0.0');
    expect(screen.queryByText('Git agent')).toBeNull();
    expect(screen.queryByLabelText('GitHub token')).toBeNull();
  });

  it('the admin sees the section with the token status and the allowed commands', async () => {
    signInAs(ADMIN);
    vi.spyOn(settingsApi, 'version').mockResolvedValue({ version: '1.0.0' });
    vi.spyOn(settingsApi, 'getSystem').mockResolvedValue(gitSystem);
    renderWithProviders(<SystemSettingsModal open onClose={() => undefined} />);
    expect(await screen.findByText('Git agent')).toBeTruthy();
    expect(screen.getByText('Not configured.')).toBeTruthy();
    expect((screen.getByRole('checkbox', { name: 'status' }) as HTMLInputElement).checked).toBe(true);
    expect((screen.getByRole('checkbox', { name: 'diff' }) as HTMLInputElement).checked).toBe(false);
  });

  it('saving a token posts it once, empties the field and reports it saved', async () => {
    signInAs(ADMIN);
    vi.spyOn(settingsApi, 'version').mockResolvedValue({ version: '1.0.0' });
    vi.spyOn(settingsApi, 'getSystem').mockResolvedValue(gitSystem);
    const save = vi.spyOn(settingsApi, 'saveGitToken').mockResolvedValue(new Response(null));
    renderWithProviders(<SystemSettingsModal open onClose={() => undefined} />);
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
    signInAs(ADMIN);
    vi.spyOn(settingsApi, 'version').mockResolvedValue({ version: '1.0.0' });
    const save = mockSavingServer();
    renderWithProviders(<SystemSettingsModal open onClose={() => undefined} />);
    fireEvent.click(await screen.findByRole('checkbox', { name: 'diff' }));
    await waitFor(() => expect(save).toHaveBeenCalledWith(['status', 'diff']));
    await waitFor(() => expect((screen.getByRole('checkbox', { name: 'status' }) as HTMLInputElement).disabled).toBe(false));
    fireEvent.click(screen.getByRole('checkbox', { name: 'status' }));
    await waitFor(() => expect(save).toHaveBeenLastCalledWith(['diff']));
  });

  it('a failed save puts the checkbox back and says so', async () => {
    signInAs(ADMIN);
    vi.spyOn(settingsApi, 'version').mockResolvedValue({ version: '1.0.0' });
    vi.spyOn(settingsApi, 'getSystem').mockResolvedValue(gitSystem);
    vi.spyOn(settingsApi, 'saveGitAllowedCommands').mockRejectedValue(new Error('nope'));
    renderWithProviders(<SystemSettingsModal open onClose={() => undefined} />);
    const box = (await screen.findByRole('checkbox', { name: 'commit' })) as HTMLInputElement;
    fireEvent.click(box);
    await waitFor(() => expect(box.checked).toBe(false));
  });

  it('the command boxes are locked while a save is in flight', async () => {
    signInAs(ADMIN);
    vi.spyOn(settingsApi, 'version').mockResolvedValue({ version: '1.0.0' });
    vi.spyOn(settingsApi, 'getSystem').mockResolvedValue(gitSystem);
    let release: () => void = () => undefined;
    vi.spyOn(settingsApi, 'saveGitAllowedCommands').mockImplementation(
      () => new Promise<Response>((resolve) => (release = () => resolve(new Response(null)))),
    );
    renderWithProviders(<SystemSettingsModal open onClose={() => undefined} />);
    fireEvent.click(await screen.findByRole('checkbox', { name: 'diff' }));
    await waitFor(() => expect((screen.getByRole('checkbox', { name: 'commit' }) as HTMLInputElement).disabled).toBe(true));
    release();
    await waitFor(() => expect((screen.getByRole('checkbox', { name: 'commit' }) as HTMLInputElement).disabled).toBe(false));
  });

  it('a failed token save says why and keeps what was typed', async () => {
    signInAs(ADMIN);
    vi.spyOn(settingsApi, 'version').mockResolvedValue({ version: '1.0.0' });
    vi.spyOn(settingsApi, 'getSystem').mockResolvedValue(gitSystem);
    vi.spyOn(settingsApi, 'saveGitToken').mockRejectedValue(new Error('bad token'));
    renderWithProviders(<SystemSettingsModal open onClose={() => undefined} />);
    const field = (await screen.findByLabelText('GitHub token')) as HTMLInputElement;
    fireEvent.change(field, { target: { value: 'ghp_abc' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save token' }));
    expect(await screen.findByText('bad token')).toBeTruthy();
    expect(field.value).toBe('ghp_abc');
  });

  it('a failed save goes back to the last saved list, not to the one the page loaded with', async () => {
    signInAs(ADMIN);
    vi.spyOn(settingsApi, 'version').mockResolvedValue({ version: '1.0.0' });
    const save = mockSavingServer('commit');
    renderWithProviders(<SystemSettingsModal open onClose={() => undefined} />);
    const diff = (await screen.findByRole('checkbox', { name: 'diff' })) as HTMLInputElement;
    const commit = screen.getByRole('checkbox', { name: 'commit' }) as HTMLInputElement;
    fireEvent.click(diff);
    await waitFor(() => expect(save).toHaveBeenCalledTimes(1));
    fireEvent.click(commit);
    await waitFor(() => expect(commit.checked).toBe(false));
    expect(diff.checked).toBe(true);
  });

  it('the max tokens, thinking budget and user preferences defaults are saved to the store', async () => {
    signInAs(USER);
    vi.spyOn(settingsApi, 'version').mockResolvedValue({ version: '1.0.0' });
    useSettingsStore.getState().hydrate();
    renderWithProviders(<SystemSettingsModal open onClose={() => undefined} />);
    const tokens = await screen.findByLabelText('Max tokens value');
    fireEvent.focus(tokens);
    fireEvent.change(tokens, { target: { value: '2048' } });
    fireEvent.blur(tokens);
    const budget = screen.getByLabelText('Thinking budget value');
    fireEvent.focus(budget);
    fireEvent.change(budget, { target: { value: '1500' } });
    fireEvent.blur(budget);
    const before = useSettingsStore.getState().defaults.userPreferences;
    fireEvent.click(screen.getByRole('switch', { name: 'User preferences' }));
    const d = useSettingsStore.getState().defaults;
    expect(d.sampling.max_tokens).toBe(2048);
    expect(d.sampling.thinking_budget_tokens).toBe(1500);
    expect(d.userPreferences).toBe(!before);
  });

  it('changing a default calls setDefaults and is the next new chat\'s starting value', async () => {
    signInAs(USER);
    vi.spyOn(settingsApi, 'version').mockResolvedValue({ version: '1.0.0' });
    useSettingsStore.getState().hydrate();
    renderWithProviders(<SystemSettingsModal open onClose={() => undefined} />);
    fireEvent.click(await screen.findByRole('combobox', { name: 'Default thinking profile' }));
    fireEvent.click(screen.getByRole('option', { name: /None/ }));
    expect(useSettingsStore.getState().defaults.sampling.thinking_profile).toBe('none');
    useSettingsStore.getState().resetToDefaults(); // what opening the home page does
    expect(useSettingsStore.getState().sampling).toMatchObject({ thinking_profile: 'none', enable_thinking: false });
  });
});
