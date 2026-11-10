import { create } from 'zustand';

/**
 * Which thought boxes the user has expanded, by `chatId:ordinal` (the ordinal is the number of user
 * turns up to the one the reply answers). The key is the same for the live reply and for the saved
 * one, so a box stays open when the turn finishes and when the chat is refetched.
 */
interface ThoughtState {
  expanded: Record<string, true>;
  toggle: (key: string) => void;
  /** Forgets every box of one chat (the ordinals shift when a turn is deleted). */
  clearChat: (chatId: string) => void;
}

export function thoughtKey(chatId: string, ordinal: number): string {
  return `${chatId}:${ordinal}`;
}

export const useThoughtStore = create<ThoughtState>((set) => ({
  expanded: {},
  toggle: (key) =>
    set((state) => {
      const next = { ...state.expanded };
      if (next[key]) delete next[key];
      else next[key] = true;
      return { expanded: next };
    }),
  clearChat: (chatId) =>
    set((state) => {
      const prefix = `${chatId}:`;
      const next: Record<string, true> = {};
      for (const key of Object.keys(state.expanded)) {
        if (!key.startsWith(prefix)) next[key] = true;
      }
      return { expanded: next };
    }),
}));
