import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import { chatsApi } from '../../../api/chats';
import { modelsApi, personasApi } from '../../../api/settings';
import { resetSaveLight, useSaveLight } from '../../../lib/save-light';
import { initUserStorage } from '../../../lib/user-storage';
import { useSettingsStore } from '../../../state/settings-store';
import { useUserStore } from '../../../state/user-store';
import { renderWithProviders } from '../../../test/render';
import { ChatSection } from './ChatSection';

const ADMIN = { id: 'a1', email: 'a@x', role: 'admin' } as const;
const store = () => useSettingsStore.getState();

describe('ChatSection', () => {
  beforeEach(() => {
    localStorage.clear();
    initUserStorage(ADMIN);
    useUserStore.setState({ user: ADMIN });
    store().hydrate();
    store().resetToDefaults();
    resetSaveLight();
    vi.spyOn(modelsApi, 'list').mockResolvedValue([
      { id: 'm1', name: 'Model 1' },
      { id: 'm2', name: 'Model 2' },
    ] as never);
    vi.spyOn(personasApi, 'list').mockResolvedValue([
      { id: 'p1', name: 'Careful reviewer' },
    ] as never);
  });
  afterEach(() => {
    vi.restoreAllMocks();
    store().resetToDefaults();
  });

  it('choosing a model keeps it at once and lights Saved', async () => {
    renderWithProviders(<ChatSection />);
    expect(useSaveLight.getState().state).toBe('idle');
    fireEvent.click(screen.getByRole('combobox', { name: 'Model' }));
    fireEvent.click(await screen.findByRole('option', { name: /m2/ }));
    expect(store().model).toBe('m2');
    expect(useSaveLight.getState().state).toBe('saved');
  });

  it('the thinking profile is a choice of three; None turns thinking off', () => {
    renderWithProviders(<ChatSection />);
    const group = screen.getByRole('radiogroup', { name: 'Thinking profile' });
    fireEvent.click(within(group).getByRole('radio', { name: 'None' }));
    expect(store().sampling.thinking_profile).toBe('none');
    expect(store().sampling.enable_thinking).toBe(false);
  });

  it('a persona can be chosen and taken off again', async () => {
    renderWithProviders(<ChatSection />);
    await waitFor(() => expect(personasApi.list).toHaveBeenCalled());
    fireEvent.click(screen.getByRole('combobox', { name: 'Persona' }));
    fireEvent.click(await screen.findByRole('option', { name: 'Careful reviewer' }));
    expect(store().personaId).toBe('p1');
    fireEvent.click(screen.getByRole('combobox', { name: 'Persona' }));
    fireEvent.click(screen.getByRole('option', { name: 'None' }));
    expect(store().personaId).toBeNull();
  });

  it('memory use, the longest answer and the thinking budget go to the store', () => {
    renderWithProviders(<ChatSection />);
    fireEvent.click(screen.getByRole('switch', { name: /Use what it remembers about you/ }));
    expect(store().userPreferences).toBe(false);
    fireEvent.change(screen.getByRole('slider', { name: 'Longest answer' }), {
      target: { value: '2048' },
    });
    expect(store().sampling.max_tokens).toBe(2048);
    fireEvent.change(screen.getByRole('slider', { name: 'Thinking budget' }), {
      target: { value: '500' },
    });
    expect(store().sampling.thinking_budget_tokens).toBe(500);
  });

  it('temperature and top P stay with the model while their boxes are empty, and can go back', () => {
    renderWithProviders(<ChatSection />);
    expect(store().sampling.temperature).toBeUndefined();
    const temperature = screen.getByRole('spinbutton', { name: 'Temperature' });
    expect(temperature).toHaveAttribute('placeholder', 'model default');
    expect(temperature).toHaveValue(null);
    fireEvent.change(temperature, { target: { value: '0.4' } });
    expect(store().sampling.temperature).toBe(0.4);
    fireEvent.change(temperature, { target: { value: '9' } });
    expect(store().sampling.temperature).toBe(2);
    fireEvent.change(temperature, { target: { value: '' } });
    expect(store().sampling.temperature).toBeUndefined();
    fireEvent.change(screen.getByRole('spinbutton', { name: 'Top P' }), {
      target: { value: '0.9' },
    });
    expect(store().sampling.top_p).toBe(0.9);
  });

  it('away from a chat there is one set of values: what every new chat starts with', () => {
    renderWithProviders(<ChatSection />);
    expect(screen.getByText(/what every new chat starts with/)).toBeTruthy();
    expect(screen.queryByText('New chats start with')).toBeNull();
    fireEvent.change(screen.getByRole('slider', { name: 'Longest answer' }), {
      target: { value: '1024' },
    });
    expect(store().defaults.sampling.max_tokens).toBe(1024);
  });

  it('over a chat it says whose values these are, and lists what new chats start with apart', async () => {
    vi.spyOn(chatsApi, 'get').mockResolvedValue({
      id: 'c1',
      title: 'Flaky login test',
      messages: [],
    } as never);
    store().enterChat();
    renderWithProviders(<ChatSection />, { route: '/chat/c1', path: '/chat/:chatId' });
    expect(await screen.findByText(/These apply to "Flaky login test"/)).toBeTruthy();
    expect(screen.getByText('New chats start with')).toBeTruthy();

    // The chat's own value changes; the starting value of new chats does not.
    const before = store().defaults.sampling.max_tokens;
    fireEvent.change(screen.getByRole('slider', { name: 'Longest answer' }), {
      target: { value: '512' },
    });
    expect(store().sampling.max_tokens).toBe(512);
    expect(store().defaults.sampling.max_tokens).toBe(before);

    // And the other way round.
    fireEvent.change(screen.getByRole('slider', { name: 'Longest answer in new chats' }), {
      target: { value: '2048' },
    });
    fireEvent.change(screen.getByRole('slider', { name: 'Thinking budget in new chats' }), {
      target: { value: '300' },
    });
    fireEvent.click(
      within(screen.getByRole('radiogroup', { name: 'Thinking profile for new chats' })).getByRole(
        'radio',
        {
          name: 'Precision',
        },
      ),
    );
    const memory = screen.getAllByRole('switch', { name: /Use what it remembers about you/ })[1];
    if (!memory) throw new Error('the memory switch is missing');
    fireEvent.click(memory);
    expect(store().defaults.sampling.max_tokens).toBe(2048);
    expect(store().defaults.sampling.thinking_budget_tokens).toBe(300);
    expect(store().defaults.sampling.thinking_profile).toBe('precision');
    expect(store().defaults.userPreferences).toBe(false);
    expect(store().sampling.max_tokens).toBe(512);
  });
});
