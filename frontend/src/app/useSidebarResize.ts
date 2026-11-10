import {
  useCallback,
  useEffect,
  useState,
  type KeyboardEvent,
  type PointerEvent,
  type RefObject,
} from 'react';
import {
  clampSidebarWidth,
  SIDEBAR_MAX_WIDTH,
  SIDEBAR_MIN_WIDTH,
  useUiStore,
} from '../state/ui-store';

/** Pixels an arrow key moves the sidebar edge. */
export const RESIZE_KEY_STEP = 16;
const PHONE_MAX_WIDTH = 768;

/**
 * Resizing of the sidebar by its right edge: pointer drag and arrow keys (as a separator). The width is
 * remembered by the store. Like the legacy page, `--sidebar-width` follows the sidebar's real width (0 on a phone)
 * so `main` keeps clear of it, and the expanded width is published as `--sidebar-expanded-width`.
 */
export function useSidebarResize(aside: RefObject<HTMLElement | null>) {
  const width = useUiStore((s) => s.sidebarWidth);
  const collapsed = useUiStore((s) => s.sidebarCollapsed);
  const setWidth = useUiStore((s) => s.setSidebarWidth);
  const [resizing, setResizing] = useState(false);

  useEffect(() => {
    document.documentElement.style.setProperty('--sidebar-expanded-width', `${width}px`);
  }, [width]);

  // Mirror the legacy `syncSidebarWidth`: main's left margin is the sidebar's measured width.
  useEffect(() => {
    const el = aside.current;
    if (!el) return undefined;
    const root = document.documentElement;
    const sync = () =>
      root.style.setProperty(
        '--sidebar-width',
        window.innerWidth <= 768 ? '0px' : `${el.getBoundingClientRect().width}px`,
      );
    sync();
    window.addEventListener('resize', sync);
    const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(sync);
    observer?.observe(el);
    return () => {
      window.removeEventListener('resize', sync);
      observer?.disconnect();
      root.style.removeProperty('--sidebar-width');
    };
  }, [aside, collapsed, width]);

  const onPointerDown = useCallback((event: PointerEvent<HTMLElement>) => {
    // The collapsed rail and the phone drawer have a fixed width.
    if (useUiStore.getState().sidebarCollapsed || window.innerWidth <= PHONE_MAX_WIDTH) return;
    // jsdom has no pointer capture; browsers always do.
    event.currentTarget.setPointerCapture?.(event.pointerId);
    setResizing(true);
  }, []);
  const onPointerMove = useCallback(
    (event: PointerEvent<HTMLElement>) => {
      // The edge follows the pointer: the width is its distance from the sidebar's left edge.
      if (resizing) setWidth(event.clientX - (aside.current?.getBoundingClientRect().left ?? 0));
    },
    [aside, resizing, setWidth],
  );
  const onPointerUp = useCallback((event: PointerEvent<HTMLElement>) => {
    event.currentTarget.releasePointerCapture?.(event.pointerId); // absent in jsdom
    setResizing(false);
  }, []);
  const onKeyDown = useCallback(
    (event: KeyboardEvent<HTMLElement>) => {
      if (window.innerWidth <= PHONE_MAX_WIDTH) return;
      const current = useUiStore.getState().sidebarWidth;
      if (event.key === 'ArrowLeft') setWidth(current - RESIZE_KEY_STEP);
      else if (event.key === 'ArrowRight') setWidth(current + RESIZE_KEY_STEP);
      else if (event.key === 'Home') setWidth(SIDEBAR_MIN_WIDTH);
      else if (event.key === 'End') setWidth(SIDEBAR_MAX_WIDTH);
      else return;
      event.preventDefault();
    },
    [setWidth],
  );

  return {
    resizing,
    handleProps: {
      role: 'separator' as const,
      'aria-orientation': 'vertical' as const,
      'aria-label': 'Resize sidebar',
      'aria-valuemin': SIDEBAR_MIN_WIDTH,
      'aria-valuemax': SIDEBAR_MAX_WIDTH,
      'aria-valuenow': clampSidebarWidth(width),
      tabIndex: collapsed ? -1 : 0,
      onPointerDown,
      onPointerMove,
      onPointerUp,
      onPointerCancel: onPointerUp,
      onKeyDown,
    },
  };
}
