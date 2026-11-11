import { beforeEach, describe, expect, it } from 'vitest';
import { markSaved, resetSaveLight, trackSave, useSaveLight } from './save-light';

const state = () => useSaveLight.getState().state;

describe('the save light', () => {
  beforeEach(resetSaveLight);

  it('shows nothing until something is saved; a setting kept on the device is saved at once', () => {
    expect(state()).toBe('idle');
    markSaved();
    expect(state()).toBe('saved');
  });

  it('says Saving while a save runs, then Saved', async () => {
    let finish: () => void = () => undefined;
    const save = trackSave(new Promise<void>((resolve) => (finish = resolve)));
    expect(state()).toBe('saving');
    markSaved(); // a device setting changed meanwhile: the light keeps saying Saving
    expect(state()).toBe('saving');
    finish();
    await save;
    expect(state()).toBe('saved');
  });

  it('stays on Saving until the last of several saves has ended', async () => {
    let first: () => void = () => undefined;
    let second: () => void = () => undefined;
    const a = trackSave(new Promise<void>((resolve) => (first = resolve)));
    const b = trackSave(new Promise<void>((resolve) => (second = resolve)));
    first();
    await a;
    expect(state()).toBe('saving');
    second();
    await b;
    expect(state()).toBe('saved');
  });

  it('says Not saved when a save fails, and hands the error back to the caller', async () => {
    const failing = trackSave(Promise.reject(new Error('offline')));
    await expect(failing).rejects.toThrow('offline');
    expect(state()).toBe('error');
    await trackSave(Promise.resolve());
    expect(state()).toBe('saved');
  });

  it('a failure is not hidden by another save that was already running', async () => {
    let finish: () => void = () => undefined;
    const slow = trackSave(new Promise<void>((resolve) => (finish = resolve)));
    await trackSave(Promise.reject(new Error('x'))).catch(() => undefined);
    finish();
    await slow;
    expect(state()).toBe('error');
  });
});
