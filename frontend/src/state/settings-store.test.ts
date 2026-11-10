import { beforeEach, describe, expect, it } from 'vitest';
import { DEFAULT_SAMPLING, KEYS, useSettingsStore } from './settings-store';
import { useUserStore } from './user-store';
import { initUserStorage } from '../lib/user-storage';

const ADMIN = { id: 'a1', email: 'a@x', role: 'admin' } as const;
const USER_1 = { id: 'u1', email: 'u1@x', role: 'user' } as const;
const USER_2 = { id: 'u2', email: 'u2@x', role: 'user' } as const;

function signIn(user: typeof ADMIN | typeof USER_1 | typeof USER_2) {
  initUserStorage(user);
  useUserStore.setState({ user });
  useSettingsStore.getState().hydrate();
}

describe('settings store with per-user storage', () => {
  beforeEach(() => localStorage.clear());

  it("keeps two users' settings apart and never touches the admin's keys", () => {
    signIn(USER_1);
    useSettingsStore.getState().setModel('m1', 'Model 1');
    useSettingsStore.getState().setPersona('p1');
    useSettingsStore.getState().setSampling({ max_tokens: 111 });
    signIn(USER_2);
    expect(useSettingsStore.getState().model).toBeNull();
    expect(useSettingsStore.getState().personaId).toBeNull();
    expect(useSettingsStore.getState().sampling).toEqual(DEFAULT_SAMPLING);
    useSettingsStore.getState().setModel('m2', 'Model 2');
    signIn(USER_1);
    expect(useSettingsStore.getState().model).toBe('m1');
    expect(useSettingsStore.getState().personaId).toBe('p1');
    expect(useSettingsStore.getState().sampling.max_tokens).toBe(111);
    expect(localStorage.getItem(KEYS.model)).toBeNull(); // the admin's key is untouched
    expect(localStorage.getItem(`${KEYS.model}:u2`)).toBe('m2');
  });

  it('the admin reads and writes the existing key names, so existing values load unchanged', () => {
    localStorage.setItem(KEYS.model, 'old-model');
    localStorage.setItem(KEYS.modelName, 'Old model');
    localStorage.setItem(KEYS.research, 'true');
    signIn(ADMIN);
    expect(useSettingsStore.getState().model).toBe('old-model');
    expect(useSettingsStore.getState().modes.researchMode).toBe(true);
    useSettingsStore.getState().setVisionEnabled(true);
    expect(localStorage.getItem(KEYS.vision)).toBe('true');
  });

  it('starts from defaults and does not read storage until hydrate()', () => {
    initUserStorage(ADMIN);
    localStorage.setItem(KEYS.model, 'x');
    useSettingsStore.setState({ model: null });
    expect(useSettingsStore.getState().model).toBeNull();
    useSettingsStore.getState().hydrate();
    expect(useSettingsStore.getState().model).toBe('x');
  });

  it('git mode starts off and a user cannot turn it on', () => {
    signIn(USER_1);
    useSettingsStore.getState().setMode('gitMode', true);
    expect(useSettingsStore.getState().modes.gitMode).toBe(false);
    signIn(ADMIN);
    useSettingsStore.getState().setMode('gitMode', true);
    expect(useSettingsStore.getState().modes.gitMode).toBe(true);
    useSettingsStore.getState().hydrate();
    expect(useSettingsStore.getState().modes.gitMode).toBe(false);
  });
});

describe('per-chat settings', () => {
  const models = [{ id: 'm-chat' }, { id: 'm-other' }];
  const detail = (over: Record<string, unknown> = {}) =>
    ({ id: 'c1', title: 't', messages: [], ...over }) as never;

  beforeEach(() => localStorage.clear());

  it('corrupt my_ai_modes storage falls back to the defaults instead of breaking start-up', () => {
    for (const bad of ['null', '"x"', '[1]', '{bad', '{"fileSystemMode":"yes"}']) {
      localStorage.setItem('my_ai_modes', bad);
      signIn(ADMIN);
      expect(useSettingsStore.getState().modes).toMatchObject({
        fileSystemMode: false,
        browsingMode: false,
        codeExecutionMode: true,
      });
    }
  });

  it('mode toggles survive a reload', () => {
    signIn(ADMIN);
    useSettingsStore.getState().setMode('fileSystemMode', true);
    useSettingsStore.getState().setMode('browsingMode', true);
    useSettingsStore.getState().setMode('codeExecutionMode', false);
    signIn(ADMIN); // a fresh page load hydrates again
    expect(useSettingsStore.getState().modes).toMatchObject({
      fileSystemMode: true,
      browsingMode: true,
      codeExecutionMode: false,
      gitMode: false,
    });
    expect(JSON.parse(localStorage.getItem('my_ai_modes') ?? '{}')).toEqual({
      fileSystemMode: true,
      browsingMode: true,
      codeExecutionMode: false,
    });
  });

  it('user preferences are stored in the legacy defaults object and keep its other fields', () => {
    localStorage.setItem(
      'my_ai_chat_defaults',
      JSON.stringify({ maxTokens: 1234, userPreferences: true }),
    );
    signIn(ADMIN);
    useSettingsStore.getState().setUserPreferences(false);
    expect(JSON.parse(localStorage.getItem('my_ai_chat_defaults') ?? '{}')).toEqual({
      maxTokens: 1234,
      userPreferences: false,
    });
    signIn(ADMIN);
    expect(useSettingsStore.getState().userPreferences).toBe(false);
  });

  it('non-admin per-chat keys carry the user suffix', () => {
    signIn(USER_1);
    useSettingsStore.getState().setMode('fileSystemMode', true);
    expect(localStorage.getItem('my_ai_modes')).toBeNull();
    expect(localStorage.getItem('my_ai_modes:u1')).not.toBeNull();
  });

  it('applyChat sets modes, preferences, persona, model and sampling from the chat and leaves storage alone', () => {
    signIn(ADMIN);
    const before = { ...localStorage };
    useSettingsStore.getState().applyChat(
      detail({
        last_model: 'm-chat',
        file_system_mode: 1,
        browsing_mode: 1,
        code_execution_mode: 0,
        research_mode: 0,
        git_mode: 1,
        user_preferences: 0,
        persona_id: 'p9',
        max_tokens: 4096,
        thinking_budget_tokens: 500,
        thinking_profile: 'precision',
        temperature: 0.4,
        top_p: 0.8,
      }),
      models,
    );
    const s = useSettingsStore.getState();
    expect(s.model).toBe('m-chat');
    expect(s.modes).toMatchObject({
      fileSystemMode: true,
      browsingMode: true,
      codeExecutionMode: false,
      gitMode: true,
    });
    expect(s.userPreferences).toBe(false);
    expect(s.personaId).toBe('p9');
    expect(s.sampling).toMatchObject({
      max_tokens: 4096,
      thinking_budget_tokens: 500,
      thinking_profile: 'precision',
      enable_thinking: true,
      temperature: 0.4,
      top_p: 0.8,
    });
    expect(s.chatScoped).toBe(true);
    expect({ ...localStorage }).toEqual(before);
  });

  it('a chat with thinking profile none has thinking off, whatever the row says', () => {
    signIn(ADMIN);
    useSettingsStore
      .getState()
      .applyChat(detail({ thinking_profile: 'none', enable_thinking: 1 }), models);
    expect(useSettingsStore.getState().sampling.enable_thinking).toBe(false);
  });

  it('a stored temperature of 1.0 leaves temperature and top p on the model default', () => {
    signIn(ADMIN);
    useSettingsStore.getState().applyChat(detail({ temperature: 1, top_p: 1.0 }), models);
    expect(useSettingsStore.getState().sampling.temperature).toBeUndefined();
    expect(useSettingsStore.getState().sampling.top_p).toBeUndefined();
  });

  it('an old chat that never set temperature or top p shows the model default, not the new-chat default', () => {
    signIn(ADMIN);
    useSettingsStore.getState().setSampling({ temperature: 0.7, top_p: 0.9 });
    useSettingsStore.getState().applyChat(detail({ temperature: 1.0, top_p: 1 }), models);
    expect(useSettingsStore.getState().sampling.temperature).toBeUndefined();
    expect(useSettingsStore.getState().sampling.top_p).toBeUndefined();
    useSettingsStore.getState().resetToDefaults();
    expect(useSettingsStore.getState().sampling.temperature).toBe(0.7);
  });

  it('a detail without temperature or top p (a seeded new chat) leaves them as they are', () => {
    signIn(ADMIN);
    useSettingsStore.getState().setSampling({ temperature: 0.7 });
    useSettingsStore.getState().applyChat(detail({}), models);
    expect(useSettingsStore.getState().sampling.temperature).toBe(0.7);
  });

  it('skips absent values, including the "None" placeholder, and a model that is not in the list', () => {
    signIn(ADMIN);
    useSettingsStore.getState().setModel('keep-me', 'keep-me');
    useSettingsStore
      .getState()
      .applyChat(
        detail({
          last_model: 'not-installed',
          persona_id: 'None',
          file_system_mode: 'None',
          max_tokens: null,
        }),
        models,
      );
    const s = useSettingsStore.getState();
    expect(s.model).toBe('keep-me');
    expect(s.personaId).toBeNull();
    expect(s.modes.fileSystemMode).toBe(false);
    expect(s.sampling.max_tokens).toBe(DEFAULT_SAMPLING.max_tokens);
  });

  it('a user never gets git mode from a chat', () => {
    signIn(USER_1);
    useSettingsStore.getState().applyChat(detail({ git_mode: 1 }), models);
    expect(useSettingsStore.getState().modes.gitMode).toBe(false);
  });

  it('setters after applyChat change the active values but not the defaults or storage', () => {
    signIn(ADMIN);
    useSettingsStore.getState().applyChat(detail({}), models);
    useSettingsStore.getState().setMode('fileSystemMode', true);
    useSettingsStore.getState().setModel('m-other', 'm-other');
    useSettingsStore.getState().setSampling({ max_tokens: 999 });
    useSettingsStore.getState().setPersona('p1');
    expect(useSettingsStore.getState().modes.fileSystemMode).toBe(true);
    expect(localStorage.getItem('my_ai_modes')).toBeNull();
    expect(localStorage.getItem(KEYS.model)).toBeNull();
    expect(localStorage.getItem(KEYS.sampling)).toBeNull();
    expect(localStorage.getItem(KEYS.persona)).toBeNull();
    expect(useSettingsStore.getState().defaults.modes.fileSystemMode).toBe(false);
  });

  it('resetToDefaults restores the saved defaults and leaves chat scope', () => {
    signIn(ADMIN);
    useSettingsStore.getState().setSampling({ max_tokens: 2048 });
    useSettingsStore.getState().applyChat(detail({ max_tokens: 111, file_system_mode: 1 }), models);
    expect(useSettingsStore.getState().sampling.max_tokens).toBe(111);
    useSettingsStore.getState().resetToDefaults();
    expect(useSettingsStore.getState().sampling.max_tokens).toBe(2048);
    expect(useSettingsStore.getState().modes.fileSystemMode).toBe(false);
    expect(useSettingsStore.getState().chatScoped).toBe(false);
  });

  it('hydrating a sampling value saved before the fix ({none, thinking on}) turns thinking off in the active values and the defaults', () => {
    localStorage.setItem(
      KEYS.sampling,
      JSON.stringify({ thinking_profile: 'none', enable_thinking: true }),
    );
    signIn(ADMIN);
    expect(useSettingsStore.getState().sampling.enable_thinking).toBe(false);
    expect(useSettingsStore.getState().defaults.sampling.enable_thinking).toBe(false);
  });

  it('a chat with no persona (null) clears the default persona; a partial detail leaves it alone', () => {
    signIn(ADMIN);
    useSettingsStore.getState().setPersona('p-default');
    useSettingsStore.getState().applyChat(detail({ persona_id: null }), models);
    expect(useSettingsStore.getState().personaId).toBeNull();
    useSettingsStore.getState().resetToDefaults();
    expect(useSettingsStore.getState().personaId).toBe('p-default');
    useSettingsStore.getState().applyChat(detail({}), models); // seeded detail: no persona_id key
    expect(useSettingsStore.getState().personaId).toBe('p-default');
    useSettingsStore.getState().resetToDefaults();
    useSettingsStore.getState().applyChat(detail({ persona_id: 'None' }), models);
    expect(useSettingsStore.getState().personaId).toBeNull();
  });

  it('entering a chat makes setters chat-scoped before its values have loaded', () => {
    signIn(ADMIN);
    useSettingsStore.getState().enterChat();
    useSettingsStore.getState().setMode('browsingMode', true);
    expect(localStorage.getItem('my_ai_modes')).toBeNull();
    expect(useSettingsStore.getState().defaults.modes.browsingMode).toBe(false);
    useSettingsStore.getState().resetToDefaults();
    expect(useSettingsStore.getState().modes.browsingMode).toBe(false);
  });

  it('choosing the thinking profile none turns thinking off and a profile that thinks turns it on', () => {
    signIn(ADMIN);
    useSettingsStore.getState().setSampling({ thinking_profile: 'none' });
    expect(useSettingsStore.getState().sampling.enable_thinking).toBe(false);
    expect(JSON.parse(localStorage.getItem(KEYS.sampling) ?? '{}').enable_thinking).toBe(false);
    useSettingsStore.getState().setSampling({ thinking_profile: 'precision' });
    expect(useSettingsStore.getState().sampling.enable_thinking).toBe(true);
  });
});

describe('new-chat defaults from System Settings', () => {
  beforeEach(() => localStorage.clear());

  it('changes the stored defaults and the active values, persists them, and derives thinking from the profile', () => {
    signIn(ADMIN);
    useSettingsStore.getState().setDefaults({ thinking_profile: 'none', userPreferences: false, max_tokens: 4096, thinking_budget_tokens: 500 });
    const s = useSettingsStore.getState();
    expect(s.sampling).toMatchObject({ thinking_profile: 'none', enable_thinking: false, max_tokens: 4096, thinking_budget_tokens: 500 });
    expect(s.userPreferences).toBe(false);
    expect(s.defaults.sampling).toMatchObject({ thinking_profile: 'none', max_tokens: 4096 });
    signIn(ADMIN); // reload
    expect(useSettingsStore.getState().defaults.sampling).toMatchObject({ thinking_profile: 'none', enable_thinking: false, max_tokens: 4096 });
    expect(useSettingsStore.getState().userPreferences).toBe(false);
  });

  it('keeps the other fields of my_ai_chat_defaults', () => {
    localStorage.setItem('my_ai_chat_defaults', JSON.stringify({ maxTokens: 1234 }));
    signIn(ADMIN);
    useSettingsStore.getState().setDefaults({ userPreferences: false });
    expect(JSON.parse(localStorage.getItem('my_ai_chat_defaults') ?? '{}')).toEqual({ maxTokens: 1234, userPreferences: false });
  });

  it('leaves an open chat\'s active values alone, and the next reset yields the new defaults', () => {
    signIn(ADMIN);
    useSettingsStore.getState().applyChat({ id: 'c1', title: 't', messages: [], max_tokens: 111 } as never, []);
    useSettingsStore.getState().setDefaults({ max_tokens: 8192 });
    expect(useSettingsStore.getState().sampling.max_tokens).toBe(111);
    expect(useSettingsStore.getState().defaults.sampling.max_tokens).toBe(8192);
    useSettingsStore.getState().resetToDefaults();
    expect(useSettingsStore.getState().sampling.max_tokens).toBe(8192);
  });
});
