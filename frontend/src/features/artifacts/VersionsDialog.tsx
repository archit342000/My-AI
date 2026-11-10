import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { artifactsApi, type ScopeRef, type VersionDiff } from '../../api/filesystem';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { ConfirmDialog } from '../../components/ui/ConfirmDialog';
import { Modal } from '../../components/ui/Modal';
import { showToast } from '../../components/ui/toast-store';
import { diffRows, diffSummary } from '../../lib/diff-lines';

const LINE_CLASS = {
  added: 'versions__line versions__line--added',
  removed: 'versions__line versions__line--removed',
} as const;

type Shown =
  | { kind: 'content'; version: number; content: string }
  | { kind: 'diff'; version: number; diff: VersionDiff };

/** Version history: view any version, compare it with the current one, restore it. Every call reports its failure. */
export function VersionsDialog({
  open,
  onClose,
  artifactId,
  scope,
  onRestored,
}: {
  open: boolean;
  onClose: () => void;
  artifactId: string;
  scope: ScopeRef;
  onRestored: () => void;
}) {
  const versions = useQuery({
    queryKey: ['versions', artifactId],
    queryFn: () => artifactsApi.versions(artifactId, scope),
    enabled: open,
  });
  const currentVersion = useQuery({
    queryKey: ['version-current', artifactId],
    queryFn: () => artifactsApi.currentVersion(artifactId, scope),
    enabled: open,
  });
  const [shown, setShown] = useState<Shown | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [restoring, setRestoring] = useState<number | null>(null);
  const current = currentVersion.data ?? null;

  async function view(version: number) {
    setError(null);
    try {
      const v = await artifactsApi.version(artifactId, version, scope);
      setShown({ kind: 'content', version, content: v.content });
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load that version');
    }
  }

  async function compare(version: number) {
    if (current === null) return;
    setError(null);
    try {
      const diff = await artifactsApi.diff(artifactId, version, current, scope);
      setShown({ kind: 'diff', version, diff });
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not compare the versions');
    }
  }

  async function restore(version: number) {
    setRestoring(null);
    try {
      await artifactsApi.restore(artifactId, version, scope);
      showToast(`Restored version ${version}`, 'success');
      onRestored();
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Restore failed');
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Version history" maxWidth={720}>
      {versions.isPending ? <p className="versions__status">Loading…</p> : null}
      {versions.isError ? (
        <p className="versions__error" role="alert">
          {versions.error instanceof Error ? versions.error.message : 'Could not load the versions'}
        </p>
      ) : null}
      {currentVersion.isError ? (
        <p className="versions__error" role="alert">
          Could not tell which version is current, so comparing is unavailable
          {currentVersion.error instanceof Error ? `: ${currentVersion.error.message}` : ''}.
        </p>
      ) : null}
      {versions.data && versions.data.length === 0 ? <p className="versions__status">No earlier versions.</p> : null}
      <ul className="versions__list">
        {(versions.data ?? []).map((v) => (
          <li key={v.version_number} className="versions__item">
            <span className="versions__label">
              v{v.version_number} · {v.author} · {new Date(v.timestamp * 1000).toLocaleString()}
              {v.comment ? ` — ${v.comment}` : ''}
              {v.version_number === current ? <Badge tone="accent">Current</Badge> : null}
            </span>
            <Button size="sm" variant="secondary" onClick={() => void view(v.version_number)}>
              View
            </Button>
            <Button
              size="sm"
              variant="secondary"
              disabled={current === null || v.version_number === current}
              onClick={() => void compare(v.version_number)}
            >
              Compare with current
            </Button>
            <Button
              size="sm"
              variant="secondary"
              disabled={v.version_number === current}
              onClick={() => setRestoring(v.version_number)}
            >
              Restore
            </Button>
          </li>
        ))}
      </ul>
      {error ? (
        <p className="versions__error" role="alert">
          {error}
        </p>
      ) : null}
      {shown?.kind === 'content' ? (
        <pre className="versions__preview font-mono" aria-label={`Version ${shown.version}`}>
          {shown.content}
        </pre>
      ) : null}
      {shown?.kind === 'diff' ? (
        <div className="versions__diff" aria-label={`Version ${shown.version} compared with the current one`}>
          <p className="versions__status">{diffSummary(shown.diff)}</p>
          <pre className="font-mono versions__lines">
            {diffRows(shown.diff).map((row, i) => (
              <span key={i} className={LINE_CLASS[row.kind]}>
                {row.kind === 'added' ? '+ ' : '- '}
                {row.text}
                {'\n'}
              </span>
            ))}
          </pre>
        </div>
      ) : null}
      <ConfirmDialog
        open={restoring !== null}
        title="Restore this version?"
        message={`Version ${restoring ?? ''} becomes the current content of the file. Later versions are kept.`}
        confirmLabel="Restore"
        onCancel={() => setRestoring(null)}
        onConfirm={() => void restore(restoring ?? 0)}
      />
    </Modal>
  );
}
