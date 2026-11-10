import { act, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { artifactsApi } from '../../api/filesystem';
import { renderWithProviders } from '../../test/render';
import { ArtifactDrawer } from './ArtifactDrawer';

const setWidth = (value: number) =>
  Object.defineProperty(window, 'innerWidth', { configurable: true, value });
const panelWidth = () =>
  (screen.getByRole('complementary', { name: 'Files' }) as HTMLElement).style.getPropertyValue(
    '--artifact-width',
  );
const press = (key: string) =>
  act(() => {
    screen
      .getByRole('separator', { name: 'Drag to resize the files panel' })
      .dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true }));
  });

afterEach(() => {
  vi.restoreAllMocks();
  setWidth(1024);
  localStorage.removeItem('my_ai_artifact_width');
  document.getElementById('app-root')?.remove();
});

describe('ArtifactDrawer', () => {
  it('is a panel named Files, at its default width', () => {
    vi.spyOn(artifactsApi, 'list').mockResolvedValue([]);
    setWidth(1440);
    renderWithProviders(<ArtifactDrawer scope={{ chatId: 'c1' }} />);
    expect(panelWidth()).toBe('400px');
    expect(screen.getByRole('heading', { name: 'Files' })).toBeTruthy();
  });

  it('joins the app frame as a panel of its own, beside the content panel', () => {
    vi.spyOn(artifactsApi, 'list').mockResolvedValue([]);
    const frame = document.createElement('div');
    frame.id = 'app-root';
    document.body.appendChild(frame);
    renderWithProviders(<ArtifactDrawer scope={{ chatId: 'c1' }} />);
    expect(frame.contains(screen.getByRole('complementary', { name: 'Files' }))).toBe(true);
  });

  it('the arrow keys resize it and the width is remembered', () => {
    vi.spyOn(artifactsApi, 'list').mockResolvedValue([]);
    setWidth(1440);
    const first = renderWithProviders(<ArtifactDrawer scope={{ chatId: 'c1' }} />);
    press('ArrowLeft');
    expect(panelWidth()).toBe('416px');
    press('ArrowRight');
    press('ArrowRight');
    expect(panelWidth()).toBe('384px');
    first.unmount();
    renderWithProviders(<ArtifactDrawer scope={{ chatId: 'c1' }} />);
    expect(panelWidth()).toBe('384px');
  });

  it('cannot take the whole window: the chat keeps a column', () => {
    vi.spyOn(artifactsApi, 'list').mockResolvedValue([]);
    localStorage.setItem('my_ai_artifact_width', '960');
    setWidth(1280);
    renderWithProviders(<ArtifactDrawer scope={{ chatId: 'c1' }} />);
    expect(1280 - Number.parseInt(panelWidth(), 10)).toBeGreaterThanOrEqual(360);
  });

  it('never goes below its smallest width, even in a narrow window', () => {
    vi.spyOn(artifactsApi, 'list').mockResolvedValue([]);
    setWidth(700);
    renderWithProviders(<ArtifactDrawer scope={{ chatId: 'c1' }} />);
    for (let i = 0; i < 10; i++) press('ArrowRight');
    expect(panelWidth()).toBe('320px');
  });
});
