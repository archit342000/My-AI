import { create } from 'zustand';
import type { LiveTurn } from '../features/chat/stream-reducer';
import type { UploadedFile } from '../api/completions';

/** A user message shown before the server has persisted it. */
export interface PendingUser {
  text: string;
  images: string[];
  files: UploadedFile[];
}

/**
 * A turn that ended early. The partial reply is kept on the client (the server may not have
 * persisted it), so the reader still sees what arrived, with a "Stopped" marker or the error and a
 * Retry action.
 */
export interface InterruptedTurn {
  chatId: string;
  live: LiveTurn;
  kind: 'stopped' | 'error';
  /** Error message for `kind: 'error'`. */
  message: string | null;
}

export interface StreamState {
  /** Chat whose turn is in flight, or null when idle. */
  chatId: string | null;
  live: LiveTurn | null;
  pending: PendingUser | null;
  interrupted: InterruptedTurn | null;
  controller: AbortController | null;
  /** True from the moment Stop is pressed until the turn has finished, which follows the stop answer. */
  stopping: boolean;
  setStopping: (stopping: boolean) => void;
  start: (chatId: string, pending: PendingUser | null, controller: AbortController) => void;
  update: (live: LiveTurn) => void;
  /** Ends the in-flight turn as stopped or failed, keeping the partial reply. Call before `finish`. */
  interrupt: (turn: Omit<InterruptedTurn, 'chatId'> & { chatId: string }) => void;
  dismissInterrupted: () => void;
  finish: () => void;
}

export const useStreamStore = create<StreamState>((set) => ({
  chatId: null,
  live: null,
  pending: null,
  interrupted: null,
  controller: null,
  stopping: false,
  setStopping: (stopping) => set({ stopping }),
  start: (chatId, pending, controller) =>
    set({ chatId, pending, controller, interrupted: null, live: null, stopping: false }),
  update: (live) => set({ live }),
  interrupt: (turn) => set({ interrupted: turn }),
  dismissInterrupted: () => set({ interrupted: null }),
  finish: () => set({ chatId: null, live: null, pending: null, controller: null, stopping: false }),
}));
