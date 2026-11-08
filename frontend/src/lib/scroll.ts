/** Smart autoscroll helpers, ported from legacy `scroll-manager.js`. */

export const NEAR_BOTTOM_PX = 60;
export const SCROLL_THROTTLE_MS = 100;

/** True when the user is within `threshold` px of the end, meaning they are following the stream. */
export function isNearBottom(el: HTMLElement, threshold = NEAR_BOTTOM_PX): boolean {
  return el.scrollHeight - el.scrollTop <= el.clientHeight + threshold;
}

/**
 * Keyboard offset for the chat input on touch devices: how far the on-screen keyboard covers the
 * layout viewport. Offsets under 10px are ignored to avoid jitter.
 */
export function computeKeyboardOffset(innerHeight: number, visualHeight: number): number {
  const offset = innerHeight - visualHeight;
  return offset > 10 ? offset : 0;
}

/** Throttled scroll-to-bottom. Returns true when a scroll was scheduled. */
export function createAutoScroller(now: () => number = Date.now) {
  let last = 0;
  return function scrollToBottom(el: HTMLElement, opts: { forced?: boolean; smooth?: boolean } = {}) {
    const t = now();
    if (!opts.forced && t - last < SCROLL_THROTTLE_MS) return false;
    last = t;
    if (!opts.forced && !isNearBottom(el)) return false;
    requestAnimationFrame(() => {
      el.scrollTo({ top: el.scrollHeight, behavior: opts.smooth ? 'smooth' : 'auto' });
    });
    return true;
  };
}
