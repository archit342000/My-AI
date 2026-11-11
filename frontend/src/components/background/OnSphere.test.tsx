import { act, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { OnSphere } from './OnSphere';

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe('OnSphere', () => {
  it('renders its words inside the marked container, with a hidden fade layer', () => {
    render(
      <OnSphere className="greeting">
        <h1>Hello there</h1>
      </OnSphere>,
    );
    const host = screen.getByRole('heading', { name: 'Hello there' }).parentElement;
    expect(host).toHaveClass('on-sphere', 'greeting');
    expect(host?.querySelector('.fade-layer')).toHaveAttribute('aria-hidden', 'true');
  });

  it('draws a patch behind each button it measures', () => {
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function (
      this: HTMLElement,
    ) {
      const box =
        this.tagName === 'BUTTON'
          ? { left: 20, top: 30, width: 100, height: 44 }
          : { left: 0, top: 0, width: 400, height: 200 };
      return {
        ...box,
        right: box.left + box.width,
        bottom: box.top + box.height,
        x: box.left,
        y: box.top,
        toJSON: () => box,
      };
    });
    const { container } = render(
      <OnSphere>
        <button type="button">See my work</button>
      </OnSphere>,
    );
    const patches = container.querySelectorAll('.fade-layer i');
    expect(patches).toHaveLength(1);
    expect((patches[0] as HTMLElement).style.width).toBe(
      `${100 + 2 * Math.min(14, Math.max(8, 44 * 0.14))}px`,
    );
  });
  it('measures again when the size changes and when the typefaces have loaded', async () => {
    let width = 100;
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function (
      this: HTMLElement,
    ) {
      const box =
        this.tagName === 'BUTTON'
          ? { left: 20, top: 30, width, height: 44 }
          : { left: 0, top: 0, width: 400, height: 200 };
      return {
        ...box,
        right: box.left + box.width,
        bottom: box.top + box.height,
        x: box.left,
        y: box.top,
        toJSON: () => box,
      };
    });
    const resized: Array<() => void> = [];
    vi.stubGlobal(
      'ResizeObserver',
      class {
        constructor(callback: () => void) {
          resized.push(callback);
        }
        observe() {}
        disconnect() {}
      },
    );
    let fontsLoaded: () => void = () => {};
    const ready = new Promise<void>((resolve) => {
      fontsLoaded = resolve;
    });
    Object.defineProperty(document, 'fonts', { configurable: true, value: { ready } });
    const { container } = render(
      <OnSphere>
        <button type="button">See my work</button>
      </OnSphere>,
    );
    const patchWidth = () => (container.querySelector('.fade-layer i') as HTMLElement).style.width;
    const first = patchWidth();

    width = 160;
    act(() => resized.forEach((callback) => callback()));
    const second = patchWidth();
    expect(Number.parseFloat(second)).toBe(Number.parseFloat(first) + 60);

    width = 200;
    await act(async () => {
      fontsLoaded();
      await ready;
    });
    expect(Number.parseFloat(patchWidth())).toBe(Number.parseFloat(first) + 100);
    Reflect.deleteProperty(document, 'fonts');
  });
});
