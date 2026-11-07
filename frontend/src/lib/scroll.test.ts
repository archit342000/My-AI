import { describe, expect, it, vi } from 'vitest';
import { computeKeyboardOffset, createAutoScroller, isNearBottom } from './scroll';

function fakeEl(scrollHeight: number, scrollTop: number, clientHeight: number) {
  return { scrollHeight, scrollTop, clientHeight, scrollTo: vi.fn() } as unknown as HTMLElement & { scrollTo: ReturnType<typeof vi.fn> };
}

describe('isNearBottom', () => {
  it('is true within the 60px threshold and false beyond it', () => {
    expect(isNearBottom(fakeEl(1000, 300, 600))).toBe(false); // 1000-300-600 = 100 > 60
    expect(isNearBottom(fakeEl(1000, 350, 600))).toBe(true); // 50 <= 60
  });
});

describe('computeKeyboardOffset', () => {
  it('ignores offsets of 10px or less and returns larger ones', () => {
    expect(computeKeyboardOffset(900, 895)).toBe(0);
    expect(computeKeyboardOffset(900, 600)).toBe(300);
  });
});

describe('createAutoScroller', () => {
  it('does not scroll when the user has scrolled up, unless forced', () => {
    vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => { cb(0); return 0; });
    const scroll = createAutoScroller(() => 1000);
    const el = fakeEl(1000, 0, 600);
    expect(scroll(el)).toBe(false);
    expect(scroll(el, { forced: true })).toBe(true);
    expect(el.scrollTo).toHaveBeenCalledWith({ top: 1000, behavior: 'auto' });
    vi.unstubAllGlobals();
  });
});
