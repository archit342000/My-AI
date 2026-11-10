/**
 * Body scroll lock for modals (Safari/iOS-safe). Counted, so nested modals keep the page locked
 * until the last one closes. Mirrors the legacy `setScrollLock` behaviour.
 */
let lockCount = 0;
let savedY = 0;

export function isIOS(): boolean {
  if (typeof navigator === 'undefined') return false;
  return (
    /iPad|iPhone|iPod/.test(navigator.userAgent) ||
    (navigator.maxTouchPoints > 1 && /Macintosh/.test(navigator.userAgent))
  );
}

export function lockScroll(): void {
  lockCount += 1;
  if (lockCount > 1) return;
  const body = document.body;
  savedY = window.scrollY;
  if (!isIOS()) {
    body.style.position = 'fixed';
    body.style.top = `-${savedY}px`;
    body.style.width = '100%';
  }
  body.classList.add('no-scroll');
}

export function unlockScroll(): void {
  if (lockCount === 0) return;
  lockCount -= 1;
  if (lockCount > 0) return;
  const body = document.body;
  body.classList.remove('no-scroll');
  if (!isIOS()) {
    body.style.position = '';
    body.style.top = '';
    body.style.width = '';
    window.scrollTo(0, savedY);
  }
}

export function scrollLockDepth(): number {
  return lockCount;
}

/**
 * The areas that may scroll on iOS. A touch that starts anywhere else is prevented, so the page itself cannot
 * rubber-band (legacy `initScrollManager`). These are the legacy entries that exist in the React app, plus the
 * React scroll areas that legacy had under other names or not at all (files panel, popover lists, logs).
 */
export const SCROLL_AREAS = [
  '#messages',
  '.modal-body',
  '.cm-scroller',
  '.sidebar-content',
  '.thought-body-inner',
  '.composer-chips',
  '#chat-textarea',
  '.workspace-view',
  '.artifact-panel',
  '.artifact-drawer',
  '.ui-popover',
  '.logs-main',
].join(', ');

/** True when a touch on `target` is inside a scroll area (so it must not be prevented). */
export function isScrollAreaTarget(target: EventTarget | null): boolean {
  return target instanceof Element && target.closest(SCROLL_AREAS) !== null;
}
