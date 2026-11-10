import { fireEvent, render, screen } from '@testing-library/react';
import { useRef } from 'react';
import { afterEach, describe, expect, it } from 'vitest';
import {
  SIDEBAR_DEFAULT_WIDTH,
  SIDEBAR_MAX_WIDTH,
  SIDEBAR_MIN_WIDTH,
  useUiStore,
} from '../state/ui-store';
import { RESIZE_KEY_STEP, useSidebarResize } from './useSidebarResize';

// jsdom has no PointerEvent: a mouse event of the pointer type carries the coordinates React reads.
const pointer = (type: string, clientX = 0) =>
  new MouseEvent(type, { bubbles: true, cancelable: true, clientX });

function Harness() {
  const aside = useRef<HTMLElement>(null);
  const { handleProps, resizing } = useSidebarResize(aside);
  return (
    <aside ref={aside} data-resizing={resizing}>
      <div data-testid="handle" {...handleProps} />
    </aside>
  );
}

afterEach(() => {
  Object.defineProperty(window, 'innerWidth', { configurable: true, value: 1024 });
  useUiStore.setState({ sidebarWidth: SIDEBAR_DEFAULT_WIDTH, sidebarCollapsed: false });
  localStorage.removeItem('my_ai_sidebar_width');
  document.documentElement.style.removeProperty('--sidebar-expanded-width');
});

describe('useSidebarResize', () => {
  it('the handle is a vertical separator with the width range and publishes the width', () => {
    render(<Harness />);
    const handle = screen.getByRole('separator', { name: 'Resize sidebar' });
    expect(handle.getAttribute('aria-orientation')).toBe('vertical');
    expect(handle.getAttribute('aria-valuenow')).toBe(String(SIDEBAR_DEFAULT_WIDTH));
    expect(handle.getAttribute('aria-valuemin')).toBe(String(SIDEBAR_MIN_WIDTH));
    expect(document.documentElement.style.getPropertyValue('--sidebar-expanded-width')).toBe(
      `${SIDEBAR_DEFAULT_WIDTH}px`,
    );
  });

  it('dragging sets the width within the clamp', () => {
    render(<Harness />);
    const handle = screen.getByTestId('handle');
    fireEvent(handle, pointer('pointerdown'));
    fireEvent(handle, pointer('pointermove', 320));
    expect(useUiStore.getState().sidebarWidth).toBe(320);
    fireEvent(handle, pointer('pointermove', 9999));
    expect(useUiStore.getState().sidebarWidth).toBe(SIDEBAR_MAX_WIDTH);
    fireEvent(handle, pointer('pointerup'));
    fireEvent(handle, pointer('pointermove', 250));
    expect(useUiStore.getState().sidebarWidth).toBe(SIDEBAR_MAX_WIDTH); // not dragging any more
    expect(localStorage.getItem('my_ai_sidebar_width')).toBe(String(SIDEBAR_MAX_WIDTH));
  });

  it('arrow keys move the edge by a step, Home and End jump to the limits', () => {
    render(<Harness />);
    const handle = screen.getByTestId('handle');
    fireEvent.keyDown(handle, { key: 'ArrowRight' });
    expect(useUiStore.getState().sidebarWidth).toBe(SIDEBAR_DEFAULT_WIDTH + RESIZE_KEY_STEP);
    fireEvent.keyDown(handle, { key: 'ArrowLeft' });
    fireEvent.keyDown(handle, { key: 'ArrowLeft' });
    expect(useUiStore.getState().sidebarWidth).toBe(SIDEBAR_DEFAULT_WIDTH - RESIZE_KEY_STEP);
    fireEvent.keyDown(handle, { key: 'Home' });
    expect(useUiStore.getState().sidebarWidth).toBe(SIDEBAR_MIN_WIDTH);
    fireEvent.keyDown(handle, { key: 'End' });
    expect(useUiStore.getState().sidebarWidth).toBe(SIDEBAR_MAX_WIDTH);
  });

  it('a collapsed sidebar cannot be dragged and its handle is not focusable', () => {
    useUiStore.setState({ sidebarCollapsed: true });
    render(<Harness />);
    const handle = screen.getByTestId('handle');
    expect(handle.getAttribute('tabindex')).toBe('-1');
    fireEvent(handle, pointer('pointerdown'));
    fireEvent(handle, pointer('pointermove', 400));
    expect(useUiStore.getState().sidebarWidth).toBe(SIDEBAR_DEFAULT_WIDTH);
  });

  it('on a phone neither a drag nor the keys change the width', () => {
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 375 });
    render(<Harness />);
    const handle = screen.getByTestId('handle');
    fireEvent(handle, pointer('pointerdown'));
    fireEvent(handle, pointer('pointermove', 400));
    fireEvent.keyDown(handle, { key: 'ArrowRight' });
    expect(useUiStore.getState().sidebarWidth).toBe(SIDEBAR_DEFAULT_WIDTH);
  });
});
