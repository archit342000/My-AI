import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { backLayerDepth, pushBackLayer, resetBackLayers } from './back-layer';

const setWidth = (value: number) =>
  Object.defineProperty(window, 'innerWidth', { configurable: true, value });
/** Lets the queued bookkeeping run. */
const settle = () => new Promise<void>((resolve) => queueMicrotask(resolve));
/** The person presses Back: the browser leaves our extra step and says so. */
function pressBack() {
  window.history.replaceState({ idx: 3 }, '');
  window.dispatchEvent(new PopStateEvent('popstate', { state: { idx: 3 } }));
}

describe('back layers', () => {
  let push: ReturnType<typeof vi.spyOn>;
  let back: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    setWidth(390);
    resetBackLayers();
    window.history.replaceState({ idx: 3, key: 'k' }, '');
    push = vi.spyOn(window.history, 'pushState');
    // Our own step back: the browser would answer with a popstate a moment later.
    back = vi.spyOn(window.history, 'back').mockImplementation(() => {
      window.history.replaceState({ idx: 3, key: 'k' }, '');
      queueMicrotask(() => window.dispatchEvent(new PopStateEvent('popstate')));
    });
  });
  afterEach(() => {
    vi.restoreAllMocks();
    resetBackLayers();
    setWidth(1024);
  });

  it("adds one step while a layer is open, keeping the router's own values, and removes it when the layer closes by itself", async () => {
    const close = vi.fn();
    const release = pushBackLayer(close);
    await settle();
    expect(push).toHaveBeenCalledTimes(1);
    expect(push.mock.calls[0]?.[0]).toEqual({ idx: 3, key: 'k', backLayer: true });
    expect(backLayerDepth()).toBe(1);
    release();
    await settle();
    expect(back).toHaveBeenCalledTimes(1);
    await settle();
    expect(close).not.toHaveBeenCalled(); // its own step back is not the person pressing Back
    expect(backLayerDepth()).toBe(0);
  });

  it('Back closes the newest layer first and the step is put back while layers remain', async () => {
    const order: string[] = [];
    pushBackLayer(() => order.push('panel'));
    pushBackLayer(() => order.push('pop-up'));
    await settle();
    expect(push).toHaveBeenCalledTimes(1); // one step, however many layers
    pressBack();
    expect(order).toEqual(['pop-up']);
    await settle();
    expect(push).toHaveBeenCalledTimes(2); // armed again for the panel
    pressBack();
    expect(order).toEqual(['pop-up', 'panel']);
    await settle();
    expect(push).toHaveBeenCalledTimes(2);
    expect(back).not.toHaveBeenCalled();
    expect(backLayerDepth()).toBe(0);
  });

  it('a layer opened and closed in the same breath leaves the history alone', async () => {
    const release = pushBackLayer(() => undefined);
    release();
    pushBackLayer(() => undefined);
    await settle();
    expect(push).toHaveBeenCalledTimes(1);
    expect(back).not.toHaveBeenCalled();
  });

  it('a whole-screen wait is not closed by Back: it is told, and stays', async () => {
    const told = vi.fn();
    pushBackLayer(told, { sticky: true });
    await settle();
    pressBack();
    expect(told).toHaveBeenCalledTimes(1);
    expect(backLayerDepth()).toBe(1);
    await settle();
    expect(push).toHaveBeenCalledTimes(2); // armed again
  });

  it('after a move to another page the old step is left where it is', async () => {
    const release = pushBackLayer(() => undefined);
    await settle();
    // The router moved on: the newest entry is no longer our step.
    window.history.replaceState({ idx: 4, key: 'next' }, '');
    release();
    await settle();
    expect(back).not.toHaveBeenCalled();
  });

  it('on a wider screen Back keeps its usual meaning: nothing is registered', async () => {
    setWidth(1280);
    const release = pushBackLayer(() => undefined);
    await settle();
    expect(push).not.toHaveBeenCalled();
    expect(backLayerDepth()).toBe(0);
    release();
  });
});
