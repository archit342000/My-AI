import { describe, expect, it, vi } from 'vitest';
import { computeKeyboardOffset, createFollowController, isNearBottom } from './scroll';

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

describe('createFollowController', () => {
  it('re-pins only from a scroll position, not from content growth', () => {
    const follow = createFollowController();
    expect(follow.isPinned()).toBe(true);
    follow.observeScroll(fakeEl(1000, 400, 600));
    // The reader scrolls up: 300px away from the bottom.
    expect(follow.observeScroll(fakeEl(1000, 100, 600))).toBe(false);
    // Content grows (no scroll event): still unpinned.
    expect(follow.isPinned()).toBe(false);
    // The reader scrolls back to the bottom.
    expect(follow.observeScroll(fakeEl(1200, 580, 600))).toBe(true);
  });

  it('stays pinned through scroll events of a smooth scroll moving down', () => {
    const follow = createFollowController();
    // Content grew by 700px; a smooth scroll toward the bottom reports intermediate positions.
    expect(follow.observeScroll(fakeEl(1700, 200, 600))).toBe(true);
    expect(follow.observeScroll(fakeEl(1700, 600, 600))).toBe(true);
    expect(follow.observeScroll(fakeEl(1700, 1100, 600))).toBe(true);
  });

  it('force re-pins after a send', () => {
    const follow = createFollowController();
    follow.observeScroll(fakeEl(1000, 0, 600));
    follow.force();
    expect(follow.isPinned()).toBe(true);
  });
});
