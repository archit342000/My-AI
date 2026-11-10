import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  artifactsApi,
  type ArtifactVersion,
  type ScopeRef,
  type VersionDiff,
} from '../../api/filesystem';
import { Button, IconButton } from '../../components/ui/Button';
import { Chip } from '../../components/ui/Chip';
import { ConfirmDialog } from '../../components/ui/ConfirmDialog';
import { EmptyState } from '../../components/ui/EmptyState';
import { Notice } from '../../components/ui/Notice';
import { showToast } from '../../components/ui/toast-store';
import { Window } from '../../components/ui/Window';
import { diffRows, diffSummary } from '../../lib/diff-lines';
import { fullDateTime, whenLabel } from '../../lib/format-time';

const LINE_CLASS = {
  added: 'versions__line versions__line--added',
  removed: 'versions__line versions__line--removed',
} as const;

type Shown =
  | { kind: 'content'; version: number; content: string }
  | { kind: 'diff'; version: number; diff: VersionDiff };

/**
 * Version history: the versions on the left and the chosen one on the right (one after the other on a
 * phone). A version can be read, compared with the current one and restored. Every call says when it fails.
 */
export function VersionsDialog({
  open,
  onClose,
  artifactId,
  fileName,
  scope,
  onRestored,
}: {
  open: boolean;
  onClose: () => void;
  artifactId: string;
  /** Shown beside the title, so it is clear whose history this is. */
  fileName?: string;
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
  const [picked, setPicked] = useState<number | null>(null);
  const [shown, setShown] = useState<Shown | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [restoring, setRestoring] = useState<number | null>(null);
  const current = currentVersion.data ?? null;
  const list = versions.data ?? [];
  const chosen = list.find((v) => v.version_number === picked) ?? null;

  // A window that is opened again starts from the list.
  useEffect(() => {
    if (!open) {
      setPicked(null);
      setShown(null);
      setError(null);
    }
  }, [open]);

  async function view(version: number) {
    setPicked(version);
    setError(null);
    setLoading(true);
    try {
      const v = await artifactsApi.version(artifactId, version, scope);
      setShown({ kind: 'content', version, content: v.content });
    } catch (e) {
      setShown(null);
      setError(e instanceof Error ? e.message : 'That version could not be loaded. Try again.');
    } finally {
      setLoading(false);
    }
  }

  async function compare(version: number) {
    if (current === null) return;
    setError(null);
    setLoading(true);
    try {
      const diff = await artifactsApi.diff(artifactId, version, current, scope);
      setShown({ kind: 'diff', version, diff });
    } catch (e) {
      setError(e instanceof Error ? e.message : 'The versions could not be compared. Try again.');
    } finally {
      setLoading(false);
    }
  }

  async function restore(version: number) {
    setRestoring(null);
    try {
      await artifactsApi.restore(artifactId, version, scope);
      showToast(`Version ${version} restored`, 'success');
      onRestored();
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'That version could not be restored. Try again.');
    }
  }

  const who = (v: ArtifactVersion) =>
    [v.author, fullDateTime(v.timestamp)].filter(Boolean).join(' · ');
  const comparing = shown?.kind === 'diff' && shown.version === picked;

  return (
    <Window
      open={open}
      onClose={onClose}
      title="Version history"
      status={fileName ? <span className="font-mono versions__file">{fileName}</span> : undefined}
    >
      <div className="versions" data-view={picked === null ? 'list' : 'view'}>
        <div className="versions__list-side">
          {versions.isPending ? (
            <p className="ui-hint versions__status" role="status">
              Loading the versions
            </p>
          ) : null}
          {versions.isError ? (
            <Notice tone="bad" actionLabel="Try again" onAction={() => void versions.refetch()}>
              The versions could not be loaded.{' '}
              {versions.error instanceof Error ? versions.error.message : ''}
            </Notice>
          ) : null}
          {currentVersion.isError ? (
            <Notice tone="warn">
              It is not known which version is the current one, so versions cannot be compared.
              {currentVersion.error instanceof Error ? ` ${currentVersion.error.message}` : ''}
            </Notice>
          ) : null}
          {versions.data && list.length === 0 ? (
            <EmptyState
              title="No earlier versions"
              description="A version is kept each time the file is saved."
            />
          ) : null}
          <ul className="versions__list">
            {list.map((v) => (
              <li key={v.version_number}>
                <button
                  type="button"
                  className="versions__item"
                  aria-current={picked === v.version_number ? 'true' : undefined}
                  onClick={() => void view(v.version_number)}
                >
                  <span className="versions__item-top">
                    <span>Version {v.version_number}</span>
                    {v.version_number === current ? <Chip tint>Current</Chip> : null}
                    <time className="dat keep" title={fullDateTime(v.timestamp)}>
                      {whenLabel(v.timestamp)}
                    </time>
                  </span>
                  <span className="versions__item-note">
                    {[v.author, v.comment].filter(Boolean).join(' · ')}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>

        <div className="versions__view">
          {chosen ? (
            <>
              <div className="versions__bar">
                <IconButton
                  icon="chevron-left"
                  className="versions__back"
                  label="Back to the versions"
                  tooltip={false}
                  onClick={() => {
                    setPicked(null);
                    setShown(null);
                    setError(null);
                  }}
                />
                <div className="versions__who">
                  <span className="versions__name">Version {chosen.version_number}</span>
                  <span className="dat keep">{who(chosen)}</span>
                </div>
                <Button
                  variant="secondary"
                  size="sm"
                  aria-pressed={comparing}
                  disabled={current === null || chosen.version_number === current}
                  reason={
                    chosen.version_number === current
                      ? 'This is the current version'
                      : 'The current version is not known'
                  }
                  onClick={() =>
                    void (comparing ? view(chosen.version_number) : compare(chosen.version_number))
                  }
                >
                  Compare with current
                </Button>
                <Button
                  variant="quiet"
                  size="sm"
                  disabled={chosen.version_number === current}
                  reason="This is the current version"
                  onClick={() => setRestoring(chosen.version_number)}
                >
                  Restore
                </Button>
              </div>
              {error ? <Notice tone="bad">{error}</Notice> : null}
              {loading && !shown ? (
                <p className="ui-hint versions__status" role="status">
                  Loading version {chosen.version_number}
                </p>
              ) : null}
              {shown?.kind === 'content' ? (
                <pre
                  className="versions__preview font-mono"
                  tabIndex={0}
                  aria-label={`Version ${shown.version}`}
                >
                  {shown.content}
                </pre>
              ) : null}
              {shown?.kind === 'diff' ? (
                <div
                  className="versions__diff"
                  role="group"
                  aria-label={`Version ${shown.version} compared with the current one`}
                >
                  <p className="ui-hint versions__status">{diffSummary(shown.diff)}</p>
                  <pre className="font-mono versions__lines" tabIndex={0}>
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
            </>
          ) : list.length > 0 ? (
            <p className="versions__none">Pick a version to read it.</p>
          ) : null}
        </div>
      </div>
      <ConfirmDialog
        open={restoring !== null}
        title="Restore this version?"
        message={`Version ${restoring ?? ''} becomes the current content of the file. Later versions are kept.`}
        confirmLabel="Restore version"
        onCancel={() => setRestoring(null)}
        onConfirm={() => void restore(restoring ?? 0)}
      />
    </Window>
  );
}
