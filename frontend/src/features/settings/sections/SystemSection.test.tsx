import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import { chatsApi } from '../../../api/chats';
import { settingsApi } from '../../../api/settings';
import { useToastStore } from '../../../components/ui/toast-store';
import { resetSaveLight, useSaveLight } from '../../../lib/save-light';
import { useSettingsStore } from '../../../state/settings-store';
import { useStreamStore } from '../../../state/stream-store';
import { useUiStore } from '../../../state/ui-store';
import { renderWithProviders } from '../../../test/render';
import { ADMIN, USER, signInAs } from '../../../test/roles';
import * as sendTurnModule from '../../chat/send-turn';
import * as temporaryChatModule from '../../chat/temporary-chat';
import { SystemSection } from './SystemSection';

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
const confirmDelete = () =>
  fireEvent.click(
    within(screen.getByRole('dialog', { name: 'Delete all chats?' })).getByRole('button', {
      name: 'Delete all chats',
    }),
  );
const pick = (group: string, choice: string) =>
  fireEvent.click(
    within(screen.getByRole('radiogroup', { name: group })).getByRole('radio', { name: choice }),
  );

describe('SystemSection appearance and capabilities', () => {
  beforeEach(() => {
    signInAs(USER);
    resetSaveLight();
    vi.spyOn(settingsApi, 'version').mockResolvedValue({ version: '1.0.0' });
  });
  afterEach(() => {
    vi.restoreAllMocks();
    useUiStore.getState().setThemeMode('system');
    useUiStore.getState().setGlassMode('auto');
  });

  it('theme and panels are choices of three, kept the moment they are made', () => {
    renderWithProviders(<SystemSection />);
    pick('Theme', 'Dark');
    expect(useUiStore.getState().themeMode).toBe('dark');
    expect(useSaveLight.getState().state).toBe('saved');
    pick('Panels', 'Solid');
    expect(useUiStore.getState().glassMode).toBe('solid');
    pick('Panels', 'Frosted');
    expect(useUiStore.getState().glassMode).toBe('frosted');
  });

  it('vision input is a switch', () => {
    renderWithProviders(<SystemSection />);
    const before = useSettingsStore.getState().visionEnabled;
    fireEvent.click(screen.getByRole('switch', { name: /Vision input/ }));
    expect(useSettingsStore.getState().visionEnabled).toBe(!before);
  });

  it('says the version and who is signed in', async () => {
    renderWithProviders(<SystemSection />);
    expect(
      await screen.findByText(/Version 1\.0\.0 · Signed in as user@test\.io \(user\)/),
    ).toBeTruthy();
  });
});

describe('SystemSection code runner', () => {
  beforeEach(() => {
    signInAs(ADMIN);
    resetSaveLight();
    useToastStore.setState({ toasts: [] });
  });
  afterEach(() => vi.restoreAllMocks());

  it('a user sees no code runner, and the system settings are never fetched', async () => {
    signInAs(USER);
    const getSystem = vi.spyOn(settingsApi, 'getSystem').mockResolvedValue({ ...system });
    vi.spyOn(settingsApi, 'version').mockResolvedValue({ version: '1.0.0' });
    renderWithProviders(<SystemSection />);
    await screen.findByText(/Version 1\.0\.0/);
    expect(screen.queryByText('Code runner')).toBeNull();
    expect(screen.queryByLabelText('Timeout (seconds)')).toBeNull();
    expect(getSystem).not.toHaveBeenCalled();
  });

  it('the admin sees four boxes with the shared look and no Save button', async () => {
    mockSystem();
    renderWithProviders(<SystemSection />);
    for (const label of [
      'Timeout (seconds)',
      'Memory limit',
      'Processor limit (cores)',
      'Longest output (bytes)',
    ]) {
      expect((await screen.findByLabelText(label)).className).toContain('ui-input');
    }
    expect(screen.queryByRole('button', { name: /Save/ })).toBeNull();
  });

  it('a value is kept when its box is left, without the read-only maximum', async () => {
    mockSystem({ code_runner_max_timeout: 120 });
    const save = vi
      .spyOn(settingsApi, 'saveCodeRunner')
      .mockResolvedValue(new Response(null) as never);
    renderWithProviders(<SystemSection />);
    const field = await screen.findByLabelText('Timeout (seconds)');
    fireEvent.blur(field);
    expect(save).not.toHaveBeenCalled(); // nothing changed
    fireEvent.change(field, { target: { value: '60' } });
    fireEvent.blur(field);
    await waitFor(() => expect(save).toHaveBeenCalledWith({ ...system, code_runner_timeout: 60 }));
    expect(Object.keys(save.mock.calls[0]?.[0] ?? {})).not.toContain('code_runner_max_timeout');
    await waitFor(() => expect(useSaveLight.getState().state).toBe('saved'));
  });

  it('Enter keeps a value too', async () => {
    mockSystem();
    const save = vi
      .spyOn(settingsApi, 'saveCodeRunner')
      .mockResolvedValue(new Response(null) as never);
    renderWithProviders(<SystemSection />);
    const field = await screen.findByLabelText('Memory limit');
    fireEvent.change(field, { target: { value: ' 1G ' } });
    fireEvent.keyDown(field, { key: 'Enter' });
    await waitFor(() =>
      expect(save).toHaveBeenCalledWith({ ...system, code_runner_memory_limit: '1G' }),
    );
  });

  it('a timeout above the maximum the server reports is refused where it is typed', async () => {
    mockSystem({ code_runner_max_timeout: 120 });
    const save = vi
      .spyOn(settingsApi, 'saveCodeRunner')
      .mockResolvedValue(new Response(null) as never);
    renderWithProviders(<SystemSection />);
    const field = await screen.findByLabelText('Timeout (seconds)');
    fireEvent.change(field, { target: { value: '500' } });
    fireEvent.blur(field);
    expect(screen.getByText('At most 120 seconds.')).toBeTruthy();
    fireEvent.change(field, { target: { value: '0' } });
    expect(screen.getByText('At least 1 second.')).toBeTruthy();
    expect(save).not.toHaveBeenCalled();
  });

  it('a save that fails says why and keeps what was typed', async () => {
    mockSystem();
    vi.spyOn(settingsApi, 'saveCodeRunner').mockRejectedValue(new Error('runner offline'));
    renderWithProviders(<SystemSection />);
    const field = (await screen.findByLabelText('Timeout (seconds)')) as HTMLInputElement;
    fireEvent.change(field, { target: { value: '45' } });
    fireEvent.blur(field);
    await waitFor(() =>
      expect(useToastStore.getState().toasts.some((t) => t.message === 'runner offline')).toBe(
        true,
      ),
    );
    expect(field.value).toBe('45');
    expect(useSaveLight.getState().state).toBe('error');
  });
});

describe('SystemSection delete all chats', () => {
  beforeEach(() => {
    vi.spyOn(chatsApi, 'list').mockResolvedValue([]); // no chat is running unless a test says so
  });

  afterEach(() => {
    vi.restoreAllMocks();
    useStreamStore.setState({
      chatId: null,
      live: null,
      pending: null,
      interrupted: null,
      controller: null,
    });
  });

  it('asks first, then deletes everything, refreshes the lists and goes to the empty home page', async () => {
    signInAs(USER);
    vi.spyOn(settingsApi, 'version').mockResolvedValue({ version: '1.0.0' });
    const bulk = vi.spyOn(chatsApi, 'bulkDelete').mockResolvedValue(new Response(null));
    const { client } = renderWithProviders(<SystemSection />, {
      route: '/chat/c1',
      path: '/chat/:chatId',
    });
    const invalidate = vi.spyOn(client, 'invalidateQueries');
    fireEvent.click(await screen.findByRole('button', { name: 'Delete all' }));
    expect(bulk).not.toHaveBeenCalled();
    confirmDelete();
    await waitFor(() => expect(bulk).toHaveBeenCalledTimes(1));
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['chats'] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['workspaces'] });
    expect(await screen.findByTestId('elsewhere')).toBeTruthy(); // navigated away from /chat/:id
  });

  it('cancelling the confirmation deletes nothing', async () => {
    signInAs(USER);
    vi.spyOn(settingsApi, 'version').mockResolvedValue({ version: '1.0.0' });
    const bulk = vi.spyOn(chatsApi, 'bulkDelete').mockResolvedValue(new Response(null));
    renderWithProviders(<SystemSection />);
    fireEvent.click(await screen.findByRole('button', { name: 'Delete all' }));
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
    renderWithProviders(<SystemSection />);
    fireEvent.click(await screen.findByRole('button', { name: 'Delete all' }));
    confirmDelete();
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
    const stop = vi
      .spyOn(sendTurnModule, 'stopIfStreaming')
      .mockImplementation(async (id: string) => {
        order.push(`stop ${id}`);
      });
    vi.spyOn(chatsApi, 'bulkDelete').mockImplementation(async () => {
      order.push('delete');
      return new Response(null);
    });
    renderWithProviders(<SystemSection />);
    fireEvent.click(await screen.findByRole('button', { name: 'Delete all' }));
    confirmDelete();
    await waitFor(() => expect(order).toEqual(['stop other-tab', 'delete']));
    expect(stop).toHaveBeenCalledWith('other-tab', true);
  });

  it('when only the clean-up after the deletion fails, the chats are reported deleted and the page still leaves', async () => {
    signInAs(USER);
    vi.spyOn(settingsApi, 'version').mockResolvedValue({ version: '1.0.0' });
    vi.spyOn(chatsApi, 'bulkDelete').mockResolvedValue(new Response(null));
    vi.spyOn(temporaryChatModule, 'discardTemporaryChat').mockRejectedValue(
      new Error('late failure'),
    );
    renderWithProviders(<SystemSection />, { route: '/chat/c1', path: '/chat/:chatId' });
    fireEvent.click(await screen.findByRole('button', { name: 'Delete all' }));
    confirmDelete();
    await waitFor(() =>
      expect(useToastStore.getState().toasts.some((t) => t.message === 'All chats deleted')).toBe(
        true,
      ),
    );
    expect(
      useToastStore.getState().toasts.some((t) => t.message.includes('could not be refreshed')),
    ).toBe(true);
    expect(await screen.findByTestId('elsewhere')).toBeTruthy();
  });

  it('does not delete while a stop was refused and the chat is still running', async () => {
    signInAs(USER);
    vi.spyOn(settingsApi, 'version').mockResolvedValue({ version: '1.0.0' });
    vi.spyOn(chatsApi, 'list').mockResolvedValue([{ id: 'busy', is_running: true }] as never);
    vi.spyOn(sendTurnModule, 'stopIfStreaming').mockResolvedValue(undefined); // refused: it only toasts
    const bulk = vi.spyOn(chatsApi, 'bulkDelete').mockResolvedValue(new Response(null));
    renderWithProviders(<SystemSection />);
    fireEvent.click(await screen.findByRole('button', { name: 'Delete all' }));
    confirmDelete();
    await waitFor(() =>
      expect(
        useToastStore.getState().toasts.some((t) => t.message.includes('still being answered')),
      ).toBe(true),
    );
    expect(bulk).not.toHaveBeenCalled();
  });

  it('does not delete when the chat list cannot be read', async () => {
    signInAs(USER);
    vi.spyOn(settingsApi, 'version').mockResolvedValue({ version: '1.0.0' });
    vi.spyOn(chatsApi, 'list').mockRejectedValue(new Error('list down'));
    const bulk = vi.spyOn(chatsApi, 'bulkDelete').mockResolvedValue(new Response(null));
    renderWithProviders(<SystemSection />);
    fireEvent.click(await screen.findByRole('button', { name: 'Delete all' }));
    confirmDelete();
    await waitFor(() =>
      expect(useToastStore.getState().toasts.some((t) => t.message === 'list down')).toBe(true),
    );
    expect(bulk).not.toHaveBeenCalled();
  });

  it('says why when the deletion fails and stays where it is', async () => {
    signInAs(USER);
    vi.spyOn(settingsApi, 'version').mockResolvedValue({ version: '1.0.0' });
    vi.spyOn(chatsApi, 'bulkDelete').mockRejectedValue(new Error('server busy'));
    renderWithProviders(<SystemSection />);
    fireEvent.click(await screen.findByRole('button', { name: 'Delete all' }));
    confirmDelete();
    await waitFor(() =>
      expect(useToastStore.getState().toasts.some((t) => t.message === 'server busy')).toBe(true),
    );
    expect(screen.queryByTestId('elsewhere')).toBeNull();
  });
});
