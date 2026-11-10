import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { Tooltip } from './Tooltip';

afterEach(() => vi.restoreAllMocks());

describe('Tooltip placement', () => {
  it('keeps a tooltip on an anchor at the left edge inside the viewport', async () => {
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function (
      this: HTMLElement,
    ) {
      const isTip = this.getAttribute('role') === 'tooltip';
      return (
        isTip
          ? { left: 0, top: 0, width: 120, height: 30, right: 120, bottom: 30 }
          : { left: 0, top: 200, width: 20, height: 20, right: 20, bottom: 220 }
      ) as DOMRect;
    });
    render(
      <Tooltip content="Copy message">
        <button type="button">copy</button>
      </Tooltip>,
    );
    screen.getByRole('button', { name: 'copy' }).focus();
    const tip = await screen.findByRole('tooltip');
    expect(Number.parseFloat(tip.style.left)).toBeGreaterThanOrEqual(8);
    expect(tip.style.transform).toBe('');
  });

  it('flips below the anchor when there is no room above', async () => {
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function (
      this: HTMLElement,
    ) {
      const isTip = this.getAttribute('role') === 'tooltip';
      return (
        isTip
          ? { left: 0, top: 0, width: 60, height: 30, right: 60, bottom: 30 }
          : { left: 200, top: 4, width: 20, height: 20, right: 220, bottom: 24 }
      ) as DOMRect;
    });
    render(
      <Tooltip content="Hint">
        <button type="button">hint</button>
      </Tooltip>,
    );
    screen.getByRole('button', { name: 'hint' }).focus();
    const tip = await screen.findByRole('tooltip');
    expect(tip.style.top).toBe('32px');
  });
});
