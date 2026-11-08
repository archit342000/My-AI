import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { TOAST_FADE_MS, TOAST_VISIBLE_MS, showToast, useToastStore } from './toast-store';

beforeEach(() => {
  vi.useFakeTimers();
  useToastStore.setState({ toasts: [] });
});
afterEach(() => vi.useRealTimers());

describe('toast store', () => {
  it('adds a toast and fades it after the visible period, then removes it', () => {
    showToast('hello', 'success');
    expect(useToastStore.getState().toasts).toMatchObject([{ message: 'hello', type: 'success', leaving: false }]);
    vi.advanceTimersByTime(TOAST_VISIBLE_MS);
    expect(useToastStore.getState().toasts[0]?.leaving).toBe(true);
    vi.advanceTimersByTime(TOAST_FADE_MS);
    expect(useToastStore.getState().toasts).toHaveLength(0);
  });

  it('defaults to info type and keeps ids unique', () => {
    const a = showToast('a');
    const b = showToast('b');
    expect(a).not.toBe(b);
    expect(useToastStore.getState().toasts.every((t) => t.type === 'info')).toBe(true);
  });
});
