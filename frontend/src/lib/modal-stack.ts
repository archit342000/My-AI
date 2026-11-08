/**
 * Global Escape handling for stacked modals. Only the top-most modal reacts, so pressing Escape
 * inside a modal opened from another modal closes just the inner one.
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

/** Registers a modal. Returns a release function that must be called on close. */
export function pushModal(onEscape: EscapeHandler): () => void {
  if (stack.length === 0) document.addEventListener('keydown', onKeyDown);
  stack.push(onEscape);
  let released = false;
  return () => {
    if (released) return;
    released = true;
    const index = stack.lastIndexOf(onEscape);
    if (index >= 0) stack.splice(index, 1);
    if (stack.length === 0) document.removeEventListener('keydown', onKeyDown);
  };
}

export function modalDepth(): number {
  return stack.length;
}
