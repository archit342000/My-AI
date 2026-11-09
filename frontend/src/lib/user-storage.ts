/**
 * Per-user localStorage keys. The admin owns all pre-existing browser data, so the admin keeps the existing key
 * names (nothing is renamed or moved); every other user gets `<key>:<userId>`.
 *
 * The design assumes one user per page load: `UserGate` sets the user once, and a switch of identity (or an expired
 * session, which answers 401) always goes through a page reload.
 */
import type { CurrentUser } from '../api/me';

let current: Pick<CurrentUser, 'id' | 'role'> | null = null;

/** Record who is signed in. Called once by `UserGate` before anything reads or writes user settings. */
export function initUserStorage(user: Pick<CurrentUser, 'id' | 'role'>): void {
  current = { id: user.id, role: user.role };
}

export function nsKey(base: string): string {
  if (!current)
    throw new Error(
      'User storage is not initialised: nsKey() was called before the user was known',
    );
  return current.role === 'admin' ? base : `${base}:${current.id}`;
}

/** For tests. */
export function resetUserStorage(): void {
  current = null;
}
