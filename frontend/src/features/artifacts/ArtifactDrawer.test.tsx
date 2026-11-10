import { act, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { artifactsApi } from '../../api/filesystem';
import { renderWithProviders } from '../../test/render';
import { ArtifactDrawer } from './ArtifactDrawer';

const rootVar = () => document.documentElement.style.getPropertyValue('--right-sidebar-width');
const setWidth = (value: number) =>
  Object.defineProperty(window, 'innerWidth', { configurable: true, value });

afterEach(() => {
  vi.restoreAllMocks();
  setWidth(1024);
  localStorage.removeItem('my_ai_artifact_width');
  document.documentElement.style.removeProperty('--right-sidebar-width');
});

describe('ArtifactDrawer beside the chat', () => {
  it('on a wide window it publishes its width plus the edge gap, so the chat narrows, and removes it on unmount', () => {
    vi.spyOn(artifactsApi, 'list').mockResolvedValue([]);
    setWidth(1440);
    const view = renderWithProviders(<ArtifactDrawer scope={{ chatId: 'c1' }} />);
    expect(rootVar()).toBe('476px'); // 460 default + 16
    view.unmount();
    expect(rootVar()).toBe('');
  });

  it('follows the window: at 1024px and below it overlays and sets nothing', () => {
    vi.spyOn(artifactsApi, 'list').mockResolvedValue([]);
    setWidth(1000);
    renderWithProviders(<ArtifactDrawer scope={{ chatId: 'c1' }} />);
    expect(rootVar()).toBe('');
    setWidth(1400);
    act(() => window.dispatchEvent(new Event('resize')));
    expect(rootVar()).toBe('476px');
    setWidth(900);
    act(() => window.dispatchEvent(new Event('resize')));
    expect(rootVar()).toBe('');
  });

  it('a resized drawer republishes its new width', () => {
    vi.spyOn(artifactsApi, 'list').mockResolvedValue([]);
    setWidth(1440);
    renderWithProviders(<ArtifactDrawer scope={{ chatId: 'c1' }} />);
    const handle = screen.getByRole('separator', { name: 'Resize files panel' });
    act(() => {
      handle.dispatchEvent(
        new KeyboardEvent('keydown', { key: 'ArrowLeft', bubbles: true, cancelable: true }),
      );
    });
    expect(rootVar()).toBe('492px'); // 476 + one 16px key step
  });

  it('side by side starts above 1024px: 1024 overlays, 1025 narrows the chat', () => {
    vi.spyOn(artifactsApi, 'list').mockResolvedValue([]);
    setWidth(1024);
    const a = renderWithProviders(<ArtifactDrawer scope={{ chatId: 'c1' }} />);
    expect(rootVar()).toBe('');
    a.unmount();
    setWidth(1025);
    renderWithProviders(<ArtifactDrawer scope={{ chatId: 'c1' }} />);
    expect(rootVar()).not.toBe('');
  });

  it('beside the chat the drawer cannot take the whole window: the chat keeps a column', () => {
    vi.spyOn(artifactsApi, 'list').mockResolvedValue([]);
    localStorage.setItem('my_ai_artifact_width', '960');
    setWidth(1280);
    document.documentElement.style.setProperty('--sidebar-width', '256px');
    renderWithProviders(<ArtifactDrawer scope={{ chatId: 'c1' }} />);
    const reserved = Number.parseInt(rootVar(), 10);
    expect(1280 - 256 - reserved).toBeGreaterThanOrEqual(400); // room left for the chat
    document.documentElement.style.removeProperty('--sidebar-width');
  });
});
