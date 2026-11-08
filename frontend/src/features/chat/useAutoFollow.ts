import { useCallback, useEffect, useRef, useState, type RefObject } from 'react';
import { createFollowController } from '../../lib/scroll';

/**
 * Keeps a scroll container pinned to its bottom while content streams in.
 *
 * - Pinned is re-measured on scroll events only, so growth never unpins the reader.
 * - A ResizeObserver on every direct child follows growth while pinned.
 * - `chatId` change and a new `forceKey` (a sent message) re-pin and scroll to the end.
 * - `pinned` lets the caller show a "Jump to latest" control while the reader is away.
 */
export function useAutoFollow(
  ref: RefObject<HTMLElement | null>,
  chatId: string,
  forceKey: unknown,
): { pinned: boolean; jumpToLatest: () => void } {
  const follow = useRef(createFollowController());
  const [pinned, setPinned] = useState(true);

  const scrollToEnd = useCallback(() => {
    const el = ref.current;
    if (!el) return;
    // `instant` overrides the legacy `scroll-behavior: smooth` on the list, so following keeps up.
    requestAnimationFrame(() => el.scrollTo({ top: el.scrollHeight, behavior: 'instant' }));
  }, [ref]);

  useEffect(() => {
    const el = ref.current;
    if (!el) return undefined;
    const onScroll = () => setPinned(follow.current.observeScroll(el));
    el.addEventListener('scroll', onScroll, { passive: true });
    return () => el.removeEventListener('scroll', onScroll);
  }, [ref]);

  // Children change identity during streaming, so re-attach on every render (cheap: a few nodes).
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof ResizeObserver === 'undefined') return undefined;
    const observer = new ResizeObserver(() => {
      if (follow.current.isPinned()) scrollToEnd();
    });
    for (const child of Array.from(el.children)) observer.observe(child);
    return () => observer.disconnect();
  });

  const firstRun = useRef(true);
  useEffect(() => {
    if (firstRun.current) {
      firstRun.current = false;
      return;
    }
    follow.current.force();
    setPinned(true);
    scrollToEnd();
  }, [forceKey, scrollToEnd]);

  useEffect(() => {
    follow.current.force();
    setPinned(true);
    scrollToEnd();
  }, [chatId, scrollToEnd]);

  const jumpToLatest = useCallback(() => {
    follow.current.force();
    setPinned(true);
    scrollToEnd();
  }, [scrollToEnd]);

  return { pinned, jumpToLatest };
}
