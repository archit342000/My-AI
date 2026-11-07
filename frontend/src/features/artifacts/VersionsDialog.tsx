import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { artifactsApi, type ScopeRef } from '../../api/filesystem';
import { Modal } from '../../components/ui/Modal';
import { showToast } from '../../components/ui/toast-store';

/** Version history: preview any version and restore it. */
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
  const versions = useQuery({ queryKey: ['versions', artifactId], queryFn: () => artifactsApi.versions(artifactId, scope), enabled: open });
  const [preview, setPreview] = useState<{ n: number; content: string } | null>(null);

  async function show(n: number) {
    const v = await artifactsApi.version(artifactId, n, scope);
    setPreview({ n, content: v.content });
  }

  async function restore(n: number) {
    try {
      await artifactsApi.restore(artifactId, n, scope);
      showToast(`Restored version ${n}`, 'success');
      onRestored();
      onClose();
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Restore failed', 'error');
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Version history" maxWidth={720}>
      {versions.isPending ? <div style={{ color: 'var(--content-muted)' }}>Loading…</div> : null}
      {versions.data && versions.data.length === 0 ? <div style={{ color: 'var(--content-muted)' }}>No earlier versions.</div> : null}
      <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 6 }}>
        {(versions.data ?? []).map((v) => (
          <li key={v.version_number} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ flex: 1, fontSize: '0.85rem' }}>
              v{v.version_number} · {v.author} · {new Date(v.timestamp * 1000).toLocaleString()}
              {v.comment ? ` — ${v.comment}` : ''}
            </span>
            <button type="button" className="btn-secondary" onClick={() => void show(v.version_number)}>View</button>
            <button type="button" className="btn-secondary" onClick={() => void restore(v.version_number)}>Restore</button>
          </li>
        ))}
      </ul>
      {preview ? (
        <pre className="font-mono" style={{ marginTop: 12, maxHeight: 300, overflow: 'auto', whiteSpace: 'pre-wrap', fontSize: '0.75rem' }}>
          {preview.content}
        </pre>
      ) : null}
    </Modal>
  );
}
