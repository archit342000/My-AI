import { pushBackLayer } from './back-layer';

/**
 * Global Escape handling for stacked layers (pop-ups, windows, sheets, the phone drawer, the settings
 * page). Only the top-most reacts, so pressing Escape inside a pop-up opened from another closes just
 * the inner one. On a phone the same layers answer Back, newest first (`back-layer.ts`).
 */
type EscapeHandler = () => void;

const stack: EscapeHandler[] = [];

function onKeyDown(event: KeyboardEvent) {
  if (event.key !== 'Escape') return;
  const top = stack[stack.length - 1];
  if (!top) return;
  event.preventDefault();
  top();
}

/**
 * Registers a layer. Returns a release function that must be called on close. `back: false` is for a
 * layer that has an address of its own (the settings page): the browser's Back already closes it.
 */
export function pushModal(onEscape: EscapeHandler, options: { back?: boolean } = {}): () => void {
  if (stack.length === 0) document.addEventListener('keydown', onKeyDown);
  stack.push(onEscape);
  const releaseBack = options.back === false ? () => undefined : pushBackLayer(onEscape);
  let released = false;
  return () => {
    if (released) return;
    released = true;
    releaseBack();
    const index = stack.lastIndexOf(onEscape);
    if (index >= 0) stack.splice(index, 1);
    if (stack.length === 0) document.removeEventListener('keydown', onKeyDown);
  };
}

export function modalDepth(): number {
  return stack.length;
}
