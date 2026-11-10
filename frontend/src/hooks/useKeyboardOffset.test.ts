import { act, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useKeyboardOffset } from './useKeyboardOffset';

function fakeViewport(height: number, offsetTop = 0) {
  const listeners = new Map<string, Set<() => void>>();
  const vv = {
    height,
    offsetTop,
    addEventListener: vi.fn((type: string, fn: () => void) => {
      if (!listeners.has(type)) listeners.set(type, new Set());
      listeners.get(type)?.add(fn);
    }),
    removeEventListener: vi.fn((type: string, fn: () => void) => listeners.get(type)?.delete(fn)),
    fire(type: string) {
      listeners.get(type)?.forEach((fn) => fn());
    },
  };
  Object.defineProperty(window, 'visualViewport', { configurable: true, value: vv });
  return vv;
}

afterEach(() => {
  Reflect.deleteProperty(window, 'visualViewport');
  document.documentElement.style.removeProperty('--keyboard-offset');
});

describe('useKeyboardOffset', () => {
  it('is the part of the layout viewport the keyboard covers, and publishes it as a CSS variable', () => {
    const vv = fakeViewport(window.innerHeight - 300);
    const { result } = renderHook(() => useKeyboardOffset(true));
    expect(result.current).toBe(300);
    expect(document.documentElement.style.getPropertyValue('--keyboard-offset')).toBe('300px');
    vv.height = window.innerHeight;
    act(() => vv.fire('resize'));
    expect(result.current).toBe(0);
    expect(document.documentElement.style.getPropertyValue('--keyboard-offset')).toBe('0px');
  });

  it('does not count a page the browser scrolled (offsetTop) as keyboard', () => {
    fakeViewport(window.innerHeight - 300, 120);
    const { result } = renderHook(() => useKeyboardOffset(true));
    expect(result.current).toBe(180);
  });

  it('removes the variable and its listeners when unmounted', () => {
    const vv = fakeViewport(window.innerHeight - 300);
    const view = renderHook(() => useKeyboardOffset(true));
    view.unmount();
    expect(document.documentElement.style.getPropertyValue('--keyboard-offset')).toBe('');
    expect(vv.removeEventListener).toHaveBeenCalledWith('resize', expect.any(Function));
    expect(vv.removeEventListener).toHaveBeenCalledWith('scroll', expect.any(Function));
  });

  it('does nothing when disabled (a desktop)', () => {
    fakeViewport(window.innerHeight - 300);
    const { result } = renderHook(() => useKeyboardOffset(false));
    expect(result.current).toBe(0);
    expect(document.documentElement.style.getPropertyValue('--keyboard-offset')).toBe('');
  });
});
