const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/** Focusable elements inside `container`, in DOM order, skipping disabled and inert ones. */
export function focusableWithin(container: HTMLElement): HTMLElement[] {
  return Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
    (el) => !el.closest('[hidden], [inert]'),
  );
}

/**
 * Keeps Tab and Shift+Tab inside `container` until the returned release function is called. Focus
 * moves to the first focusable element on activation, and the previously focused element is
 * restored on release.
 */
export function trapFocus(container: HTMLElement): () => void {
  const previouslyFocused = document.activeElement as HTMLElement | null;
  const first = focusableWithin(container)[0];
  (first ?? container).focus();

  function onKeyDown(event: KeyboardEvent) {
    if (event.key !== 'Tab') return;
    const nodes = focusableWithin(container);
    if (nodes.length === 0) {
      event.preventDefault();
      return;
    }
    const head = nodes[0]!;
    const tail = nodes[nodes.length - 1]!;
    const active = document.activeElement;
    const outside = !(active instanceof Node) || !container.contains(active);
    if (event.shiftKey && (active === head || outside)) {
      event.preventDefault();
      tail.focus();
    } else if (!event.shiftKey && (active === tail || outside)) {
      event.preventDefault();
      head.focus();
    }
  }

  document.addEventListener('keydown', onKeyDown);
  return () => {
    document.removeEventListener('keydown', onKeyDown);
    previouslyFocused?.focus?.();
  };
}
