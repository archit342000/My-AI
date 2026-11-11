/**
 * How the rest of the app talks to the dot sphere without knowing about the canvas:
 * a ripple when something is sent or committed, a slow pulse while the app is working.
 */

export type SphereSignal = { type: 'ripple'; strength?: number } | { type: 'busy'; busy: boolean };

type Listener = (signal: SphereSignal) => void;

const listeners = new Set<Listener>();
let busy = false;

/** Subscribes to sphere signals. The current busy state is delivered at once. Returns the unsubscribe. */
export function subscribeSphere(listener: Listener): () => void {
  listeners.add(listener);
  listener({ type: 'busy', busy });
  return () => {
    listeners.delete(listener);
  };
}

/** A wave through the sphere. */
export function rippleSphere(strength?: number): void {
  listeners.forEach((listener) => listener({ type: 'ripple', strength }));
}

/** Starts or ends the working pulse. Repeating the same state does nothing. */
export function setSphereBusy(next: boolean): void {
  if (next === busy) return;
  busy = next;
  listeners.forEach((listener) => listener({ type: 'busy', busy }));
}
