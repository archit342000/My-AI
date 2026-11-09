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
