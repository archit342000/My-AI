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
}

/**
 * Saves edits by themselves: a short pause after the last change, one save at a time, the newest text
 * wins. `flush` is for the moments work could be lost (switching file, closing); leaving the screen
 * flushes too. A failed save keeps the text and is tried again on the next change or flush.
 */
export function useAutoSave(
  save: (id: string, content: string) => Promise<void>,
  delay = 800,
): AutoSave {
  const [state, setState] = useState<SaveState>('saved');
  const pending = useRef<Job | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const running = useRef<Promise<boolean> | null>(null);
  const alive = useRef(true);
  const saveRef = useRef(save);
  saveRef.current = save;

  const flush = useCallback(async (): Promise<boolean> => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
    // One save at a time: wait for the one in flight, then send the newest text.
    while (running.current) await running.current;
    const job = pending.current;
    if (!job) return true;
    pending.current = null;
    if (alive.current) setState('saving');
    const run = saveRef.current(job.id, job.content).then(
      () => {
        if (alive.current) setState(pending.current ? 'unsaved' : 'saved');
        return true;
      },
      () => {
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
    const onHide = () => void flush();
    window.addEventListener('pagehide', onHide);
    return () => {
      window.removeEventListener('pagehide', onHide);
      alive.current = false;
      void flush();
    };
  }, [flush]);

  return { state, schedule, flush };
}
