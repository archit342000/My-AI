import { renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { backLayerDepth, resetBackLayers } from '../lib/back-layer';
import { useBackLayer } from './useBackLayer';

const setWidth = (value: number) =>
  Object.defineProperty(window, 'innerWidth', { configurable: true, value });

describe('useBackLayer', () => {
  beforeEach(() => {
    setWidth(390);
    resetBackLayers();
    window.history.replaceState({ idx: 3 }, '');
    vi.spyOn(window.history, 'back').mockImplementation(() => undefined);
  });
  afterEach(() => {
    vi.restoreAllMocks();
    resetBackLayers();
    setWidth(1024);
  });

  it('registers a layer only while open, and calls the newest handler on Back', async () => {
    const first = vi.fn();
    const second = vi.fn();
    const { rerender, unmount } = renderHook(
      ({ open, onBack }: { open: boolean; onBack: () => void }) => useBackLayer(open, onBack),
      { initialProps: { open: false, onBack: first } },
    );
    expect(backLayerDepth()).toBe(0);
    rerender({ open: true, onBack: first });
    expect(backLayerDepth()).toBe(1);
    rerender({ open: true, onBack: second });
    expect(backLayerDepth()).toBe(1);
    await new Promise<void>((resolve) => queueMicrotask(resolve));
    // The person presses Back: the browser leaves the extra step and says so.
    window.history.replaceState({ idx: 3 }, '');
    window.dispatchEvent(new PopStateEvent('popstate', { state: { idx: 3 } }));
    expect(first).not.toHaveBeenCalled();
    expect(second).toHaveBeenCalledTimes(1);
    unmount();
    expect(backLayerDepth()).toBe(0);
  });

  it('does nothing on a wider screen', () => {
    setWidth(1024);
    renderHook(() => useBackLayer(true, vi.fn()));
    expect(backLayerDepth()).toBe(0);
  });
});
