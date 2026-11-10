import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useAutoSave } from './useAutoSave';

describe('useAutoSave', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it('saves once after a pause in typing, with the newest text', async () => {
    const save = vi.fn(async () => undefined);
    const { result } = renderHook(() => useAutoSave(save, 500));
    act(() => result.current.schedule('f', 'a'));
    act(() => result.current.schedule('f', 'ab'));
    expect(result.current.state).toBe('unsaved');
    await act(() => vi.advanceTimersByTimeAsync(499));
    expect(save).not.toHaveBeenCalled();
    await act(() => vi.advanceTimersByTimeAsync(1));
    expect(save).toHaveBeenCalledTimes(1);
    expect(save).toHaveBeenCalledWith('f', 'ab');
    expect(result.current.state).toBe('saved');
  });

  it('flush saves at once and reports that nothing is left', async () => {
    const save = vi.fn(async () => undefined);
    const { result } = renderHook(() => useAutoSave(save, 500));
    act(() => result.current.schedule('f', 'text'));
    let ok = false;
    await act(async () => {
      ok = await result.current.flush();
    });
    expect(ok).toBe(true);
    expect(save).toHaveBeenCalledWith('f', 'text');
    await act(() => vi.advanceTimersByTimeAsync(1000));
    expect(save).toHaveBeenCalledTimes(1);
  });

  it('flush with nothing waiting does nothing', async () => {
    const save = vi.fn(async () => undefined);
    const { result } = renderHook(() => useAutoSave(save));
    await act(async () => {
      expect(await result.current.flush()).toBe(true);
    });
    expect(save).not.toHaveBeenCalled();
  });

  it('one save at a time: text typed during a save goes out after it, and flush waits for both', async () => {
    const releases: Array<() => void> = [];
    const save = vi.fn(() => new Promise<void>((resolve) => releases.push(resolve)));
    const { result } = renderHook(() => useAutoSave(save, 500));
    act(() => result.current.schedule('f', 'one'));
    await act(() => vi.advanceTimersByTimeAsync(500));
    expect(save).toHaveBeenCalledTimes(1);
    expect(result.current.state).toBe('saving');
    act(() => result.current.schedule('f', 'two'));
    let done = false;
    let flushing: Promise<boolean> = Promise.resolve(false);
    act(() => {
      flushing = result.current.flush().then((ok) => (done = ok));
    });
    expect(save).toHaveBeenCalledTimes(1);
    await act(async () => {
      releases[0]?.();
      await Promise.resolve();
    });
    await act(() => vi.advanceTimersByTimeAsync(0));
    expect(save).toHaveBeenLastCalledWith('f', 'two');
    expect(done).toBe(false);
    await act(async () => {
      releases[1]?.();
      await flushing;
    });
    expect(done).toBe(true);
    expect(result.current.state).toBe('saved');
  });

  it('a failed save keeps the text: flush reports it and the next flush sends it again', async () => {
    const save = vi
      .fn<(id: string, content: string) => Promise<void>>()
      .mockRejectedValueOnce(new Error('offline'));
    const { result } = renderHook(() => useAutoSave(save, 500));
    act(() => result.current.schedule('f', 'text'));
    await act(async () => {
      expect(await result.current.flush()).toBe(false);
    });
    expect(result.current.state).toBe('error');
    save.mockResolvedValue(undefined);
    await act(async () => {
      expect(await result.current.flush()).toBe(true);
    });
    expect(save).toHaveBeenLastCalledWith('f', 'text');
    expect(result.current.state).toBe('saved');
  });

  it('saves what is waiting when the screen goes away', async () => {
    const save = vi.fn(async () => undefined);
    const { result, unmount } = renderHook(() => useAutoSave(save, 500));
    act(() => result.current.schedule('f', 'last words'));
    unmount();
    await vi.advanceTimersByTimeAsync(0);
    expect(save).toHaveBeenCalledWith('f', 'last words');
  });
});
