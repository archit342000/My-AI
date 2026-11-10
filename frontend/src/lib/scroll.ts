/** Smart autoscroll helpers, ported from legacy `scroll-manager.js`. */

export const NEAR_BOTTOM_PX = 60;

/** True when the user is within `threshold` px of the end, meaning they are following the stream. */
export function isNearBottom(el: HTMLElement, threshold = NEAR_BOTTOM_PX): boolean {
  return el.scrollHeight - el.scrollTop <= el.clientHeight + threshold;
}

/**
 * Keyboard offset for the chat input on touch devices: how far the on-screen keyboard covers the
 * layout viewport. `offsetTop` is how far the browser scrolled the visual viewport down (a page it
 * panned to keep the focused field visible), which is not keyboard. Offsets under 10px are ignored
 * to avoid jitter.
 */
export function computeKeyboardOffset(
  innerHeight: number,
  visualHeight: number,
  offsetTop = 0,
): number {
  const offset = innerHeight - visualHeight - offsetTop;
  return offset > 10 ? offset : 0;
}

/**
 * Follow state for a streaming transcript. `pinned` is decided only when the user scrolls (from
 * where they are at that moment), never after content grows, so one large chunk cannot unpin a
 * reader who was at the bottom. Only an upward scroll unpins: programmatic and smooth scrolls
 * toward the bottom fire scroll events mid-way and must not count as the user leaving.
 * Sending a message or opening a chat re-pins.
 */
export function createFollowController(threshold = NEAR_BOTTOM_PX) {
  let pinned = true;
  let lastTop = 0;
  return {
    isPinned: () => pinned,
    /** Call from the scroll event. Returns the new pinned state. */
    observeScroll(el: HTMLElement): boolean {
      const top = el.scrollTop;
      if (isNearBottom(el, threshold)) pinned = true;
      else if (top < lastTop - 1) pinned = false;
      lastTop = top;
      return pinned;
    },
    /** Call when the user sends a message or opens a chat. */
    force(): void {
      pinned = true;
    },
  };
}
