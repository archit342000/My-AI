import { afterEach, describe, expect, it, vi } from 'vitest';

describe('ui-store initial sidebar state (F3)', () => {
  const originalWidth = window.innerWidth;

  afterEach(() => {
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: originalWidth });
    vi.resetModules();
  });

  async function loadAtWidth(width: number) {
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: width });
    vi.resetModules();
    const mod = await import('./ui-store');
    return mod.useUiStore.getState().sidebarCollapsed;
  }

  it('starts collapsed on a phone-width viewport', async () => {
    expect(await loadAtWidth(375)).toBe(true);
  });

  it('starts expanded on a wide viewport', async () => {
    expect(await loadAtWidth(1280)).toBe(false);
  });
});
