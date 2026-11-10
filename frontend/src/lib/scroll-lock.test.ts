import { afterEach, describe, expect, it, vi } from 'vitest';
import { isIOS, isScrollAreaTarget, SCROLL_AREAS } from './scroll-lock';

afterEach(() => {
  document.body.innerHTML = '';
  vi.unstubAllGlobals();
});

describe('isScrollAreaTarget', () => {
  it('is true inside a scroll area, at any depth', () => {
    document.body.innerHTML = '<div id="messages"><p><span id="deep">x</span></p></div>';
    expect(isScrollAreaTarget(document.getElementById('deep'))).toBe(true);
    expect(isScrollAreaTarget(document.getElementById('messages'))).toBe(true);
  });

  it('is false on the page background and for no target', () => {
    document.body.innerHTML = '<div id="app-root"><button id="b">x</button></div>';
    expect(isScrollAreaTarget(document.getElementById('b'))).toBe(false);
    expect(isScrollAreaTarget(null)).toBe(false);
    expect(isScrollAreaTarget(window)).toBe(false);
  });

  it('lists the React scroll areas', () => {
    for (const area of [
      '#messages',
      '.modal-body',
      '.sidebar-content',
      '.logs-main',
      '.artifact-panel',
      '#chat-textarea',
      '.composer-chips',
    ]) {
      expect(SCROLL_AREAS).toContain(area);
    }
  });
});

describe('isIOS', () => {
  const as = (userAgent: string, maxTouchPoints: number) =>
    vi.stubGlobal('navigator', { userAgent, maxTouchPoints });
  it('is true for an iPhone and for an iPad that reports itself as a Mac', () => {
    as('Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)', 5);
    expect(isIOS()).toBe(true);
    as('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15', 5);
    expect(isIOS()).toBe(true);
  });
  it('is false for a desktop Mac (no touch) and for other desktops', () => {
    as('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15', 0);
    expect(isIOS()).toBe(false);
    as('Mozilla/5.0 (X11; Linux x86_64) Chrome/120', 0);
    expect(isIOS()).toBe(false);
  });
});
