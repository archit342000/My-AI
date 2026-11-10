import { useCallback, useEffect, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { settingsKeys, testSpeedStream } from '../../api/settings';
import {
  applySpeedEvent,
  emptySpeedTest,
  finishSpeedTest,
  type SpeedTestState,
} from '../../lib/speed-test';

export type SpeedTestPhase = 'idle' | 'running' | 'done' | 'stopped' | 'failed';

export interface UseSpeedTest {
  phase: SpeedTestPhase;
  state: SpeedTestState;
  error: string | null;
  run: (model: string, targetContext: number) => void;
  stop: () => void;
}

/** Owns one speed test run: streams the events into the reducer, and aborts on Stop and on unmount. */
export function useSpeedTest(): UseSpeedTest {
  const queryClient = useQueryClient();
  const [phase, setPhase] = useState<SpeedTestPhase>('idle');
  const [state, setState] = useState<SpeedTestState>(emptySpeedTest);
  const [error, setError] = useState<string | null>(null);
  const controller = useRef<AbortController | null>(null);

  useEffect(() => () => controller.current?.abort(), []);

  const run = useCallback(
    (model: string, targetContext: number) => {
      controller.current?.abort();
      const abort = new AbortController();
      controller.current = abort;
      let current = emptySpeedTest();
      setState(current);
      setError(null);
      setPhase('running');
      void (async () => {
        try {
          for await (const event of testSpeedStream(model, targetContext, abort.signal)) {
            if (controller.current !== abort) return;
            current = applySpeedEvent(current, event);
            setState(current);
          }
          if (controller.current !== abort) return;
          const finished = finishSpeedTest(current);
          setState(finished.state);
          setError(finished.error);
          setPhase(finished.error ? 'failed' : 'done');
        } catch (e) {
          if (controller.current !== abort) return;
          if (abort.signal.aborted) {
            setState({ ...current, status: 'Stopped' });
            setPhase('stopped');
          } else {
            setState({ ...current, status: 'Failed' });
            setError(e instanceof Error ? e.message : 'The speed test did not finish.');
            setPhase('failed');
          }
        } finally {
          // The test unloads and loads models, so the list is stale afterwards.
          if (controller.current === abort) {
            controller.current = null;
            void queryClient.invalidateQueries({ queryKey: settingsKeys.models });
          }
        }
      })();
    },
    [queryClient],
  );

  const stop = useCallback(() => controller.current?.abort(), []);

  return { phase, state, error, run, stop };
}
