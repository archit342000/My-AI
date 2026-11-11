import { IconButton } from '../../components/ui/Button';
import { StatusLight } from '../../components/ui/StatusLight';

export interface RunResult {
  state: 'running' | 'done' | 'failed';
  /** What the run printed, or why it could not run. */
  text: string;
}

/** The strip under the editor that shows what a run printed. */
export function RunOutput({ run, onClose }: { run: RunResult; onClose: () => void }) {
  return (
    <section className="fb-out" aria-label="Run output">
      <div className="fb-out__head">
        <StatusLight
          label={
            run.state === 'running'
              ? 'Running'
              : run.state === 'failed'
                ? 'Did not run'
                : 'Finished'
          }
          tone={run.state === 'failed' ? 'bad' : run.state === 'done' ? 'ok' : 'neutral'}
          busy={run.state === 'running'}
        />
        <IconButton icon="close" size="sm" label="Close the output" onClick={onClose} />
      </div>
      {/* Focusable so a long output can be scrolled from the keyboard. */}
      <pre className="fb-out__text" tabIndex={0} data-keep-scroll>
        {run.state === 'running' ? '' : run.text || 'It printed nothing.'}
      </pre>
    </section>
  );
}
