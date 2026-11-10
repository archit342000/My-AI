import { useState } from 'react';
import type { CodeRun } from '../../api/filesystem';
import { Icon } from '../../components/icons/Icon';
import { fullDateTime } from '../../lib/format-time';

type Tone = 'ok' | 'bad' | 'warn';

/** "Passed", "Failed (exit 1)" or "Timed out" for a run. */
function outcome(run: CodeRun): { label: string; tone: Tone } {
  if (run.timed_out) return { label: 'Timed out', tone: 'warn' };
  if (run.exit_code === 0) return { label: 'Passed', tone: 'ok' };
  return {
    label: run.exit_code === null ? 'Failed' : `Failed (exit ${run.exit_code})`,
    tone: 'bad',
  };
}

/** How long a run took: milliseconds under a second, seconds above. */
function took(ms: number): string {
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`;
}

/** The history stores SQLite UTC times ("2026-11-10 08:06:20"): shown as the reader's own date and time. */
function RunTime({ value }: { value: string }) {
  // SQLite times have no zone and are UTC; a value that already names a zone is used as it is.
  const hasZone = /(Z|[+-]\d{2}:?\d{2})$/i.test(value);
  const iso = `${value.replace(' ', 'T')}${hasZone ? '' : 'Z'}`;
  const shown = fullDateTime(iso);
  if (!shown) return <span className="dat keep code-run__meta">{value}</span>;
  return (
    <time className="dat keep code-run__meta" dateTime={iso}>
      {shown}
    </time>
  );
}

/**
 * One code run: a line that says the language, how it ended and its first line of code, and opens
 * to show the code, what it printed and any errors in separate blocks.
 */
export function RunCard({ run, defaultOpen = false }: { run: CodeRun; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  const { label, tone } = outcome(run);
  const firstLine = run.code.split('\n').find((line) => line.trim()) ?? '';
  return (
    <article className={open ? 'code-run code-run--open' : 'code-run'}>
      <button
        type="button"
        className="code-run__head"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <Icon name="chevron-right" size={14} className="code-run__chevron" />
        <span className={`led ${tone}`} aria-hidden="true" />
        <span className="code-run__language">{run.language}</span>
        <span className="code-run__line">{firstLine.trim()}</span>
        <span className="dat keep code-run__outcome">{label}</span>
      </button>
      {open ? (
        <div className="code-run__body">
          <div role="group" aria-label="Code" className="code-run__group">
            <pre className="font-mono code-run__block code-run__block--code">{run.code}</pre>
          </div>
          {run.stdout ? (
            <div role="group" aria-label="Output" className="code-run__group">
              <pre className="font-mono code-run__block">{run.stdout}</pre>
            </div>
          ) : null}
          {run.stderr ? (
            <div role="group" aria-label="Errors" className="code-run__group">
              <pre className="font-mono code-run__block code-run__block--error">{run.stderr}</pre>
            </div>
          ) : null}
          <div className="code-run__metas">
            {run.execution_time_ms !== null ? (
              <span className="dat keep code-run__meta">{took(run.execution_time_ms)}</span>
            ) : null}
            {run.created_at ? <RunTime value={run.created_at} /> : null}
          </div>
        </div>
      ) : null}
    </article>
  );
}
