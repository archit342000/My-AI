import { afterEach, describe, expect, it, vi } from 'vitest';
import { modalDepth, pushModal } from './modal-stack';

const releases: Array<() => void> = [];

function escape() {
  document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', cancelable: true }));
}

afterEach(() => {
  while (releases.length) releases.pop()?.();
});

describe('modal stack', () => {
  it('Escape closes only the top-most modal', () => {
    const outer = vi.fn();
    const inner = vi.fn();
    releases.push(pushModal(outer));
    releases.push(pushModal(inner));
    escape();
    expect(inner).toHaveBeenCalledTimes(1);
    expect(outer).not.toHaveBeenCalled();
  });

  it('popping the top modal reveals the one below it', () => {
    const outer = vi.fn();
    const inner = vi.fn();
    releases.push(pushModal(outer));
    const releaseInner = pushModal(inner);
    releaseInner();
    expect(modalDepth()).toBe(1);
    escape();
    expect(outer).toHaveBeenCalledTimes(1);
    expect(inner).not.toHaveBeenCalled();
  });

  it('release is idempotent and removes the modal from the stack', () => {
    const release = pushModal(() => undefined);
    release();
    release();
    expect(modalDepth()).toBe(0);
  });
});
