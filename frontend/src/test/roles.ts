import { initUserStorage } from '../lib/user-storage';
import { useUserStore } from '../state/user-store';

export const ADMIN = { id: 'admin-1', email: 'admin@test.io', role: 'admin' } as const;
export const USER = { id: 'user-1', email: 'user@test.io', role: 'user' } as const;

/** Sign a test in as the given user (the global setup signs every test in as the admin). */
export function signInAs(user: typeof ADMIN | typeof USER): void {
  initUserStorage(user);
  useUserStore.setState({ user });
}
