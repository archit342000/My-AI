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

describe('ui-store file requests', () => {
  it('openArtifact opens the drawer and records the path until it is cleared', async () => {
    const { useUiStore } = await import('./ui-store');
    useUiStore.setState({ artifactsOpen: false, requestedArtifactPath: null });
    useUiStore.getState().openArtifact('notes/hello.md');
    expect(useUiStore.getState()).toMatchObject({
      artifactsOpen: true,
      requestedArtifactPath: 'notes/hello.md',
    });
    useUiStore.getState().clearRequestedArtifact();
    expect(useUiStore.getState().requestedArtifactPath).toBeNull();
    expect(useUiStore.getState().artifactsOpen).toBe(true);
  });

  it('closing the drawer drops a request that was never answered', async () => {
    const { useUiStore } = await import('./ui-store');
    useUiStore.getState().openArtifact('late.md');
    useUiStore.getState().setArtifactsOpen(false);
    expect(useUiStore.getState().requestedArtifactPath).toBeNull();
    useUiStore.getState().openArtifact('late.md');
    useUiStore.getState().toggleArtifacts();
    expect(useUiStore.getState().requestedArtifactPath).toBeNull();
  });
});
