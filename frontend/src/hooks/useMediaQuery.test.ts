import { act, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useMediaQuery } from './useMediaQuery';

function stubMatchMedia(initial: boolean) {
  let listener: (() => void) | null = null;
  const list = {
    matches: initial,
    addEventListener: vi.fn((_: string, fn: () => void) => {
      listener = fn;
    }),
    removeEventListener: vi.fn(),
  };
  vi.stubGlobal(
    'matchMedia',
    vi.fn(() => list),
  );
  return {
    list,
    flip(next: boolean) {
      list.matches = next;
      listener?.();
    },
  };
}

afterEach(() => vi.unstubAllGlobals());

describe('useMediaQuery', () => {
  it('reports the current match and follows changes', () => {
    const media = stubMatchMedia(false);
    const { result } = renderHook(() => useMediaQuery('(max-width: 768px)'));
    expect(result.current).toBe(false);
    act(() => media.flip(true));
    expect(result.current).toBe(true);
  });

  it('stops listening when unmounted', () => {
    const media = stubMatchMedia(true);
    const { result, unmount } = renderHook(() => useMediaQuery('(max-width: 768px)'));
    expect(result.current).toBe(true);
    unmount();
    expect(media.list.removeEventListener).toHaveBeenCalledWith('change', expect.any(Function));
  });
});
