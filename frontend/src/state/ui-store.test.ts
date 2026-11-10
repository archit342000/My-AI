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

describe('remembered sidebar state', () => {
  const originalWidth = window.innerWidth;
  afterEach(() => {
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: originalWidth });
    localStorage.removeItem('my_ai_sidebar_width');
    localStorage.removeItem('my_ai_sidebar_collapsed');
    vi.resetModules();
  });
  async function load(width: number) {
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: width });
    vi.resetModules();
    return import('./ui-store');
  }

  it('the width is clamped, written to its key and read back on the next start', async () => {
    const a = await load(1280);
    a.useUiStore.getState().setSidebarWidth(5000);
    expect(a.useUiStore.getState().sidebarWidth).toBe(a.SIDEBAR_MAX_WIDTH);
    a.useUiStore.getState().setSidebarWidth(10);
    expect(a.useUiStore.getState().sidebarWidth).toBe(a.SIDEBAR_MIN_WIDTH);
    a.useUiStore.getState().setSidebarWidth(320);
    expect(localStorage.getItem('my_ai_sidebar_width')).toBe('320');
    const b = await load(1280);
    expect(b.useUiStore.getState().sidebarWidth).toBe(320);
  });

  it('on a phone a width is not set or written (the drawer has a fixed width)', async () => {
    const m = await load(375);
    m.useUiStore.getState().setSidebarWidth(400);
    expect(m.useUiStore.getState().sidebarWidth).toBe(m.SIDEBAR_DEFAULT_WIDTH);
    expect(localStorage.getItem('my_ai_sidebar_width')).toBeNull();
  });

  it('a junk stored width falls back to the default', async () => {
    localStorage.setItem('my_ai_sidebar_width', 'abc');
    const m = await load(1280);
    expect(m.useUiStore.getState().sidebarWidth).toBe(m.SIDEBAR_DEFAULT_WIDTH);
  });

  it('collapsing on a wide screen is remembered; expanding too', async () => {
    const a = await load(1280);
    a.useUiStore.getState().setSidebarCollapsed(true);
    expect(localStorage.getItem('my_ai_sidebar_collapsed')).toBe('1');
    expect((await load(1280)).useUiStore.getState().sidebarCollapsed).toBe(true);
    const b = await load(1280);
    b.useUiStore.getState().toggleSidebar();
    expect(localStorage.getItem('my_ai_sidebar_collapsed')).toBe('0');
    expect((await load(1280)).useUiStore.getState().sidebarCollapsed).toBe(false);
  });

  it('on a phone the drawer starts closed whatever is stored, and opening it is not remembered', async () => {
    localStorage.setItem('my_ai_sidebar_collapsed', '0');
    const m = await load(375);
    expect(m.useUiStore.getState().sidebarCollapsed).toBe(true);
    m.useUiStore.getState().setSidebarCollapsed(false);
    expect(localStorage.getItem('my_ai_sidebar_collapsed')).toBe('0');
    m.useUiStore.getState().setSidebarCollapsed(true);
    expect(localStorage.getItem('my_ai_sidebar_collapsed')).toBe('0'); // still the desktop choice
  });
});
