import type { CodeRun } from '../../api/filesystem';
import { Badge } from '../../components/ui/Badge';

/** "Passed", "Failed (exit 1)" or "Timed out" for a run. */
function outcome(run: CodeRun): { label: string; tone: 'success' | 'danger' | 'warning' } {
  if (run.timed_out) return { label: 'Timed out', tone: 'warning' };
  if (run.exit_code === 0) return { label: 'Passed', tone: 'success' };
  return {
    label: run.exit_code === null ? 'Failed' : `Failed (exit ${run.exit_code})`,
    tone: 'danger',
  };
}

/** The history stores SQLite UTC times ("2026-11-10 08:06:20"); show them in the reader's locale. */
function RunTime({ value }: { value: string }) {
  // SQLite times have no zone and are UTC; a value that already names a zone is used as it is.
  const hasZone = /(Z|[+-]\d{2}:?\d{2})$/i.test(value);
  const iso = `${value.replace(' ', 'T')}${hasZone ? '' : 'Z'}`;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return <span className="code-run__meta">{value}</span>;
  return (
    <time className="code-run__meta" dateTime={iso}>
      {date.toLocaleString()}
    </time>
  );
}

/** One code run: language, outcome and timing, then its code, output and errors in separate blocks. */
export function RunCard({ run }: { run: CodeRun }) {
  const { label, tone } = outcome(run);
  return (
    <article className="code-run">
      <header className="code-run__head">
        <span className="code-run__language">{run.language}</span>
        <Badge tone={tone}>{label}</Badge>
        {run.execution_time_ms !== null ? (
          <span className="code-run__meta">{run.execution_time_ms} ms</span>
        ) : null}
        {run.created_at ? <RunTime value={run.created_at} /> : null}
      </header>
      <div role="group" aria-label="Code">
        <pre className="font-mono code-run__block">{run.code}</pre>
      </div>
      {run.stdout ? (
        <div role="group" aria-label="Output">
          <pre className="font-mono code-run__block">{run.stdout}</pre>
        </div>
      ) : null}
      {run.stderr ? (
        <div role="group" aria-label="Errors">
          <pre className="font-mono code-run__block code-run__block--error">{run.stderr}</pre>
        </div>
      ) : null}
    </article>
  );
}
