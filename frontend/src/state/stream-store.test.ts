import { beforeEach, describe, expect, it } from 'vitest';
import { emptyLiveTurn } from '../features/chat/stream-reducer';
import { useStreamStore } from './stream-store';

const idle = {
  chatId: null,
  live: null,
  pending: null,
  interrupted: null,
  controller: null,
  stopping: false,
};

describe('stream store', () => {
  beforeEach(() => useStreamStore.setState(idle));

  it('start puts a chat in flight and clears an earlier interrupted turn and the stopping flag', () => {
    useStreamStore.setState({
      interrupted: { chatId: 'c1', live: emptyLiveTurn(), kind: 'stopped', message: null },
      stopping: true,
    });
    const controller = new AbortController();
    useStreamStore.getState().start('c1', { text: 'hi', images: [], files: [] }, controller);
    expect(useStreamStore.getState()).toMatchObject({
      chatId: 'c1',
      pending: { text: 'hi' },
      controller,
      interrupted: null,
      live: null,
      stopping: false,
    });
  });

  it('update replaces the live turn', () => {
    const live = { ...emptyLiveTurn(), model: 'm' };
    useStreamStore.getState().update(live);
    expect(useStreamStore.getState().live).toBe(live);
  });

  it('interrupt keeps the partial reply while the turn is still in flight', () => {
    useStreamStore.getState().start('c1', null, new AbortController());
    useStreamStore
      .getState()
      .interrupt({ chatId: 'c1', live: emptyLiveTurn(), kind: 'error', message: 'boom' });
    expect(useStreamStore.getState().chatId).toBe('c1');
    expect(useStreamStore.getState().interrupted).toMatchObject({ kind: 'error', message: 'boom' });
  });

  it('setStopping marks the stop as in progress', () => {
    useStreamStore.getState().start('c1', null, new AbortController());
    useStreamStore.getState().setStopping(true);
    expect(useStreamStore.getState().stopping).toBe(true);
  });

  it('finish makes the store idle, clears stopping and keeps the interrupted turn', () => {
    useStreamStore.getState().start('c1', null, new AbortController());
    useStreamStore.getState().setStopping(true);
    useStreamStore
      .getState()
      .interrupt({ chatId: 'c1', live: emptyLiveTurn(), kind: 'stopped', message: null });
    useStreamStore.getState().finish();
    expect(useStreamStore.getState()).toMatchObject({
      chatId: null,
      live: null,
      pending: null,
      controller: null,
      stopping: false,
    });
    expect(useStreamStore.getState().interrupted).not.toBeNull();
  });

  it('dismissInterrupted removes the partial reply', () => {
    useStreamStore.setState({
      interrupted: { chatId: 'c1', live: emptyLiveTurn(), kind: 'stopped', message: null },
    });
    useStreamStore.getState().dismissInterrupted();
    expect(useStreamStore.getState().interrupted).toBeNull();
  });
});
