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
