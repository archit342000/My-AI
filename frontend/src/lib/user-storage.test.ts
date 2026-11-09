import { afterEach, describe, expect, it } from 'vitest';
import { initUserStorage, nsKey, resetUserStorage } from './user-storage';

describe('nsKey', () => {
  afterEach(() => {
    resetUserStorage();
    initUserStorage({ id: 'admin-1', role: 'admin' });
  });

  it('throws before the user is known', () => {
    resetUserStorage();
    expect(() => nsKey('my_ai_selected_model')).toThrow(/not initialised/);
  });

  it('keeps the existing key name for the admin', () => {
    initUserStorage({ id: 'admin-1', role: 'admin' });
    expect(nsKey('my_ai_selected_model')).toBe('my_ai_selected_model');
    expect(nsKey('chatWorkspaces')).toBe('chatWorkspaces');
  });

  it('suffixes the user id for any other user, a different one per user', () => {
    initUserStorage({ id: 'u1', role: 'user' });
    const a = nsKey('my_ai_selected_model');
    initUserStorage({ id: 'u2', role: 'user' });
    const b = nsKey('my_ai_selected_model');
    expect(a).toBe('my_ai_selected_model:u1');
    expect(b).toBe('my_ai_selected_model:u2');
    expect(a).not.toBe(b);
  });
});
