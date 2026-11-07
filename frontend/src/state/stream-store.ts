import { create } from 'zustand';
import type { LiveTurn } from '../features/chat/stream-reducer';
import type { UploadedFile } from '../api/completions';

/** A user message shown before the server has persisted it. */
export interface PendingUser {
  text: string;
  images: string[];
  files: UploadedFile[];
}

export interface StreamState {
  /** Chat whose turn is in flight, or null when idle. */
  chatId: string | null;
  live: LiveTurn | null;
  pending: PendingUser | null;
  error: string | null;
  controller: AbortController | null;
  start: (chatId: string, pending: PendingUser | null, controller: AbortController) => void;
  update: (live: LiveTurn) => void;
  fail: (message: string) => void;
  finish: () => void;
}

export const useStreamStore = create<StreamState>((set) => ({
  chatId: null,
  live: null,
  pending: null,
  error: null,
  controller: null,
  start: (chatId, pending, controller) => set({ chatId, pending, controller, error: null, live: null }),
  update: (live) => set({ live }),
  fail: (message) => set({ error: message }),
  finish: () => set({ chatId: null, live: null, pending: null, controller: null }),
}));
