import { create } from 'zustand';
import type { CurrentUser } from '../api/me';

interface UserState {
  /** The signed-in user; null until `/api/me` has answered. */
  user: CurrentUser | null;
  /** A request got 401: the Access session ended and the page needs a reload. */
  sessionExpired: boolean;
  setUser: (user: CurrentUser | null) => void;
  setSessionExpired: (expired: boolean) => void;
}

export const useUserStore = create<UserState>((set) => ({
  user: null,
  sessionExpired: false,
  setUser: (user) => set({ user }),
  setSessionExpired: (sessionExpired) => set({ sessionExpired }),
}));

/** True for the admin. False for a user and while the user is still unknown (fail closed). */
export function useIsAdmin(): boolean {
  return useUserStore((s) => s.user?.role === 'admin');
}
