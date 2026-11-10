import { create } from 'zustand';

export type ToastType = 'info' | 'success' | 'error';

export interface ToastItem {
  id: number;
  message: string;
  type: ToastType;
  /** Set once the toast starts its fade-out, so the viewport can animate it out. */
  leaving: boolean;
  /** One thing the person can still do about it, usually Undo. */
  action?: ToastAction;
}

export interface ToastAction {
  label: string;
  onAction: () => void;
}

/** A brief message stays 2.6 seconds, or 6 when it offers an action such as Undo (rule book 7.11). */
export const TOAST_VISIBLE_MS = 2600;
export const TOAST_ACTION_MS = 6000;
export const TOAST_FADE_MS = 300;
/** Most toasts on screen at once; the oldest one leaves first when a new one overflows. */
export const TOAST_MAX_VISIBLE = 4;

interface ToastState {
  toasts: ToastItem[];
  show: (message: string, type?: ToastType, action?: ToastAction) => number;
  dismiss: (id: number) => void;
}

let nextId = 1;

export const useToastStore = create<ToastState>((set, get) => ({
  toasts: [],
  show: (message, type = 'info', action) => {
    const id = nextId++;
    set((s) => ({ toasts: [...s.toasts, { id, message, type, leaving: false, action }] }));
    // Errors stay until the user dismisses them, so a failure cannot be missed.
    if (type !== 'error') {
      setTimeout(() => get().dismiss(id), action ? TOAST_ACTION_MS : TOAST_VISIBLE_MS);
    }
    const active = get().toasts.filter((t) => !t.leaving);
    for (const t of active.slice(0, Math.max(0, active.length - TOAST_MAX_VISIBLE)))
      get().dismiss(t.id);
    return id;
  },
  dismiss: (id) => {
    const toast = get().toasts.find((t) => t.id === id);
    if (!toast || toast.leaving) return;
    set((s) => ({ toasts: s.toasts.map((t) => (t.id === id ? { ...t, leaving: true } : t)) }));
    setTimeout(() => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })), TOAST_FADE_MS);
  },
}));

/** Imperative helper for non-component code. Same behaviour as legacy `window.showToast`. */
export function showToast(message: string, type: ToastType = 'info', action?: ToastAction): number {
  return useToastStore.getState().show(message, type, action);
}
