import { useEffect } from 'react';
import { isIOS, isScrollAreaTarget } from '../lib/scroll-lock';

/**
 * On iOS and iPadOS: marks `<html>` with `is-ios` (the legacy stylesheet's opaque surfaces and momentum scrolling key
 * on it) and stops the page from rubber-banding by preventing touches that start outside a scroll area.
 * Does nothing elsewhere.
 */
export function usePlatformClass(): void {
  useEffect(() => {
    if (!isIOS()) return undefined;
    const root = document.documentElement;
    root.classList.add('is-ios');
    const onTouchMove = (event: TouchEvent) => {
      if (!isScrollAreaTarget(event.target)) event.preventDefault();
    };
    // Not passive: a passive listener cannot prevent the gesture.
    document.addEventListener('touchmove', onTouchMove, { passive: false });
    return () => {
      document.removeEventListener('touchmove', onTouchMove);
      root.classList.remove('is-ios');
    };
  }, []);
}
