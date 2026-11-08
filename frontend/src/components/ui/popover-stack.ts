/**
 * Stack of open popovers. Escape closes only the top-most one; the event is stopped in the capture
 * phase so an enclosing Modal does not also close. One window listener is installed while any
 * popover is open.
 */
export type PopoverCloseReason = 'escape' | 'outside';
type CloseFn = (reason: PopoverCloseReason) => void;

const stack: CloseFn[] = [];

function onKeyDown(event: KeyboardEvent) {
  if (event.key !== 'Escape' || stack.length === 0) return;
  event.stopImmediatePropagation();
  event.preventDefault();
  stack[stack.length - 1]!('escape');
}

/** Registers an open popover. Returns the release function to call when it closes. */
export function pushPopover(close: CloseFn): () => void {
  if (stack.length === 0) window.addEventListener('keydown', onKeyDown, true);
  stack.push(close);
  return () => {
    const index = stack.indexOf(close);
    if (index >= 0) stack.splice(index, 1);
    if (stack.length === 0) window.removeEventListener('keydown', onKeyDown, true);
  };
}

/** Number of open popovers (used by tests). */
export function openPopoverCount(): number {
  return stack.length;
}
