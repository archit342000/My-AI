import { useCallback, useEffect, useRef, useState } from 'react';

export type SaveState = 'saved' | 'unsaved' | 'saving' | 'error';

interface Job {
  id: string;
  content: string;
}

export interface AutoSave {
  state: SaveState;
  /** Queues the text of a file; it is saved after a short pause in typing. */
  schedule: (id: string, content: string) => void;
  /** Saves anything waiting now. Resolves true when nothing is left unsaved. */
  flush: () => Promise<boolean>;
  /** Forgets text waiting for a file that is gone (deleted), so it is not sent or retried. */
  discard: (id: string) => void;
}

export interface AutoSaveOptions {
  delay?: number;
  /** The screen went away and the last text could not be saved. */
  onLost?: () => void;
}

/**
 * Saves edits by themselves: a short pause after the last change, one save at a time, the newest text
 * wins. `flush` is for the moments work could be lost (switching file, closing); leaving the screen
 * flushes too. A failed save keeps the text and is tried again on the next change or flush.
 */
export function useAutoSave(
  save: (id: string, content: string, leaving: boolean) => Promise<void>,
  { delay = 800, onLost }: AutoSaveOptions = {},
): AutoSave {
  const [state, setState] = useState<SaveState>('saved');
  const pending = useRef<Job | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const running = useRef<Promise<boolean> | null>(null);
  const alive = useRef(true);
  /** Files that are gone: a save of one that fails is dropped, not kept for another try. */
  const gone = useRef(new Set<string>());
  const saveRef = useRef(save);
  saveRef.current = save;
  const lostRef = useRef(onLost);
  lostRef.current = onLost;

  const flush = useCallback(async (leaving = false): Promise<boolean> => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
    // One save at a time: wait for the one in flight, then send the newest text.
    while (running.current) await running.current;
    const job = pending.current;
    if (!job) return true;
    pending.current = null;
    if (alive.current) setState('saving');
    const run = saveRef.current(job.id, job.content, leaving).then(
      () => {
        if (alive.current) setState(pending.current ? 'unsaved' : 'saved');
        return true;
      },
      () => {
        if (gone.current.has(job.id)) {
          if (alive.current) setState(pending.current ? 'unsaved' : 'saved');
          return true;
        }
        // Keep the text unless newer text is already waiting.
        pending.current ??= job;
        if (alive.current) setState('error');
        return false;
      },
    );
    running.current = run;
    const ok = await run;
    if (running.current === run) running.current = null;
    return ok;
  }, []);

  const schedule = useCallback(
    (id: string, content: string) => {
      pending.current = { id, content };
      setState((s) => (s === 'saving' ? s : 'unsaved'));
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => void flush(), delay);
    },
    [delay, flush],
  );

  useEffect(() => {
    alive.current = true;
    // The page is going away: the request is marked to outlive it. (A save already in flight is
    // waited for first, so the very last text may not go out if the page is torn down at once.)
    const onHide = () => void flush(true);
    window.addEventListener('pagehide', onHide);
    return () => {
      window.removeEventListener('pagehide', onHide);
      alive.current = false;
      // The screen closed with text still waiting: save it, and say so if that fails.
      void flush().then((ok) => {
        if (!ok) lostRef.current?.();
      });
    };
  }, [flush]);

  const discard = useCallback((id: string) => {
    gone.current.add(id);
    if (pending.current?.id !== id) return;
    pending.current = null;
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
    // A save still in flight sets the light itself when it ends.
    if (!running.current) setState('saved');
  }, []);

  const flushNow = useCallback(() => flush(), [flush]);
  return { state, schedule, flush: flushNow, discard };
}
