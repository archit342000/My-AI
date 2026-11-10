import { useRef } from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { Popover } from './Popover';
import { Select } from './Select';

function stubRect(top: number, left = 100, width = 160, height = 32) {
  return vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue({
    top,
    left,
    width,
    height,
    right: left + width,
    bottom: top + height,
  } as DOMRect);
}

afterEach(() => {
  vi.restoreAllMocks();
  Reflect.deleteProperty(window, 'visualViewport');
});

describe('Popover placement', () => {
  it('a Select whose trigger is at the bottom of the viewport opens upward, anchored by its bottom edge', async () => {
    stubRect(window.innerHeight - 40);
    render(
      <Select
        aria-label="Model"
        value="a"
        onChange={() => undefined}
        options={[{ value: 'a', label: 'A' }]}
      />,
    );
    await userEvent.click(screen.getByRole('combobox', { name: 'Model' }));
    const panel = screen.getByRole('listbox');
    expect(panel.style.bottom).toBe(`${window.innerHeight - (window.innerHeight - 40) + 4}px`);
    expect(panel.style.top).toBe('');
  });

  it('a Select with room below opens downward', async () => {
    stubRect(100);
    render(
      <Select
        aria-label="Model"
        value="a"
        onChange={() => undefined}
        options={[{ value: 'a', label: 'A' }]}
      />,
    );
    await userEvent.click(screen.getByRole('combobox', { name: 'Model' }));
    const panel = screen.getByRole('listbox');
    expect(panel.style.top).toBe('136px');
    expect(panel.style.bottom).toBe('');
  });

  it('a context menu opened low on the screen opens upward from the pointer, 4px above it', () => {
    function Harness() {
      const ref = useRef<HTMLElement | null>(null);
      return (
        <Popover
          open
          anchorRef={ref}
          point={{ x: 200, y: window.innerHeight - 20 }}
          onClose={() => undefined}
          role="menu"
        >
          items
        </Popover>
      );
    }
    render(<Harness />);
    const panel = screen.getByRole('menu');
    expect(panel.style.bottom).toBe('24px');
    expect(panel.style.top).toBe('');
  });

  it('follows the visual viewport and removes every listener when it closes', () => {
    const add = vi.fn();
    const remove = vi.fn();
    Object.defineProperty(window, 'visualViewport', {
      configurable: true,
      value: {
        offsetLeft: 0,
        offsetTop: 0,
        width: 400,
        height: 500,
        addEventListener: add,
        removeEventListener: remove,
      },
    });
    const windowRemove = vi.spyOn(window, 'removeEventListener');
    stubRect(100);
    function Harness({ open }: { open: boolean }) {
      const ref = useRef<HTMLButtonElement>(null);
      return (
        <>
          <button ref={ref}>anchor</button>
          <Popover open={open} anchorRef={ref} onClose={() => undefined}>
            body
          </Popover>
        </>
      );
    }
    const { rerender } = render(<Harness open />);
    expect(add).toHaveBeenCalledWith('resize', expect.any(Function));
    expect(add).toHaveBeenCalledWith('scroll', expect.any(Function));
    // the visible height (500), not the window height, decides how much room there is
    expect((document.querySelector('.ui-popover') as HTMLElement).style.maxHeight).toBe('356px');
    rerender(<Harness open={false} />);
    expect(remove).toHaveBeenCalledWith('resize', expect.any(Function));
    expect(remove).toHaveBeenCalledWith('scroll', expect.any(Function));
    expect(windowRemove).toHaveBeenCalledWith('resize', expect.any(Function));
    expect(windowRemove).toHaveBeenCalledWith('scroll', expect.any(Function), true);
  });
});
