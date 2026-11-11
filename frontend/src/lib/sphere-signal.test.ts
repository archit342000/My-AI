import { afterEach, describe, expect, it, vi } from 'vitest';
import { rippleSphere, setSphereBusy, subscribeSphere } from './sphere-signal';

afterEach(() => setSphereBusy(false));

describe('sphere-signal', () => {
  it('tells a new listener the current busy state at once', () => {
    setSphereBusy(true);
    const listener = vi.fn();
    const off = subscribeSphere(listener);
    expect(listener).toHaveBeenCalledWith({ type: 'busy', busy: true });
    off();
  });

  it('delivers ripples and busy changes, but not a repeated state', () => {
    const listener = vi.fn();
    const off = subscribeSphere(listener);
    listener.mockClear();
    rippleSphere(2);
    setSphereBusy(true);
    setSphereBusy(true);
    setSphereBusy(false);
    expect(listener.mock.calls.map((call) => call[0])).toEqual([
      { type: 'ripple', strength: 2 },
      { type: 'busy', busy: true },
      { type: 'busy', busy: false },
    ]);
    off();
  });

  it('stops delivering after unsubscribing', () => {
    const listener = vi.fn();
    subscribeSphere(listener)();
    listener.mockClear();
    rippleSphere();
    expect(listener).not.toHaveBeenCalled();
  });
});
