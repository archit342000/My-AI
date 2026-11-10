import { create } from 'zustand';

export type SaveLightState = 'idle' | 'saving' | 'saved' | 'error';

interface SaveLight {
  state: SaveLightState;
  /** Saves in flight: the light says Saving until the last one ends. */
  pending: number;
  set: (patch: Partial<Pick<SaveLight, 'state' | 'pending'>>) => void;
}

/** The one Saving / Saved light of the settings page: every setting reports to it. */
export const useSaveLight = create<SaveLight>((set) => ({
  state: 'idle',
  pending: 0,
  set: (patch) => set(patch),
}));

/** A setting kept on this device was changed: it is saved the moment it changes. */
export function markSaved(): void {
  const { pending, set } = useSaveLight.getState();
  if (pending === 0) set({ state: 'saved' });
}

/**
 * Follows a save that goes to the server: Saving while it runs, then Saved or Not saved.
 * Returns the same promise, so the caller still sees the result or the error.
 */
export function trackSave<T>(save: Promise<T>): Promise<T> {
  const light = useSaveLight.getState();
  light.set({ state: 'saving', pending: light.pending + 1 });
  const done = (ok: boolean) => {
    const now = useSaveLight.getState();
    const pending = Math.max(0, now.pending - 1);
    // A failure stays on show even when another save ends well after it.
    const state = !ok
      ? 'error'
      : pending > 0
        ? 'saving'
        : now.state === 'error'
          ? 'error'
          : 'saved';
    now.set({ pending, state });
  };
  save.then(
    () => done(true),
    () => done(false),
  );
  return save;
}

/** Back to nothing shown (the page was opened afresh). */
export function resetSaveLight(): void {
  useSaveLight.getState().set({ state: 'idle', pending: 0 });
}
