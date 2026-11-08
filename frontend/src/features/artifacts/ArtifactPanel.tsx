import { lazy, Suspense, useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { artifactsApi, type Artifact, type ScopeRef } from '../../api/filesystem';
import { Icon } from '../../components/icons/Icon';
import { ConfirmDialog } from '../../components/ui/ConfirmDialog';
import { showToast } from '../../components/ui/toast-store';
import { Markdown } from '../../components/markdown/Markdown';
import { useUiStore } from '../../state/ui-store';
const CodeEditor = lazy(() => import('./CodeEditor').then((m) => ({ default: m.CodeEditor })));
import { previewKind } from './language';
import { VersionsDialog } from './VersionsDialog';

const scopeKey = (s: ScopeRef) => `${s.chatId ?? ''}|${s.workspaceId ?? ''}`;

/** Side panel listing a chat's or workspace's artifacts, with preview, editing, versions and export. */
export function ArtifactPanel({ scope }: { scope: ScopeRef }) {
  const queryClient = useQueryClient();
  const dark = useUiStore((s) => s.themeMode);
  const isDark = dark === 'dark' || (dark === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);
  const [selected, setSelected] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<string | null>(null);
  const [showVersions, setShowVersions] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [filter, setFilter] = useState('');
  const key = scopeKey(scope);

  const list = useQuery({
    queryKey: ['artifacts', key],
    queryFn: () => artifactsApi.list(scope),
    enabled: Boolean(scope.chatId || scope.workspaceId),
  });
  const detail = useQuery({
    queryKey: ['artifact', selected, key],
    queryFn: () => artifactsApi.get(selected as string, scope),
    enabled: Boolean(selected),
  });

  useEffect(() => {
    setDraft(null);
    setEditing(false);
  }, [selected]);

  const items = useMemo(
    () => (list.data ?? []).filter((a) => a.title.toLowerCase().includes(filter.toLowerCase())),
    [list.data, filter],
  );

  const create = useMutation({
    mutationFn: () => artifactsApi.create(scope, { title: 'Untitled', content: '', language: 'markdown' }),
    onSuccess: async (res) => {
      await queryClient.invalidateQueries({ queryKey: ['artifacts', key] });
      setSelected(res.id);
      setEditing(true);
    },
    onError: (e) => showToast(e instanceof Error ? e.message : 'Could not create file', 'error'),
  });

  const save = useMutation({
    mutationFn: (content: string) => artifactsApi.update(selected as string, scope, { content }),
    onSuccess: async () => {
      showToast('Saved', 'success');
      setDraft(null);
      await queryClient.invalidateQueries({ queryKey: ['artifact', selected, key] });
    },
    onError: (e) => showToast(e instanceof Error ? e.message : 'Save failed', 'error'),
  });

  const remove = useMutation({
    mutationFn: (id: string) => artifactsApi.remove(id, scope),
    onSuccess: async () => {
      setSelected(null);
      await queryClient.invalidateQueries({ queryKey: ['artifacts', key] });
    },
  });

  const current = detail.data;
  const content = draft ?? current?.content ?? '';
  const dirty = draft !== null && draft !== current?.content;

  return (
    <aside className="artifact-panel" aria-label="Artifacts" style={{ display: 'flex', flexDirection: 'column', height: '100%', minWidth: 0 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 12px' }}>
        <input
          aria-label="Filter artifacts"
          placeholder="Filter…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          style={{ flex: 1, minWidth: 0, padding: '6px 8px', borderRadius: 8, border: '1px solid var(--glass-border)', background: 'var(--glass-surface)', color: 'var(--content-primary)' }}
        />
        <button type="button" className="btn-ghost" aria-label="New file" onClick={() => create.mutate()}><Icon name="plus" size={16} /></button>
      </div>

      <ul style={{ listStyle: 'none', margin: 0, padding: '0 8px', maxHeight: selected ? 180 : undefined, overflowY: 'auto' }}>
        {items.map((a: Artifact) =>
          a.type === 'directory' || !a.id ? (
            <li key={`dir:${a.filename}`} style={{ padding: '6px 8px', fontSize: '0.8rem', color: 'var(--content-muted)' }}>
              <Icon name="folder" size={14} /> {a.title}
            </li>
          ) : (
          <li key={a.id}>
            <button
              type="button"
              className={`artifact-item${selected === a.id ? ' active' : ''}`}
              aria-current={selected === a.id}
              onClick={() => setSelected(a.id)}
              style={{ width: '100%', textAlign: 'left', padding: '6px 8px', borderRadius: 8, background: selected === a.id ? 'var(--accent-subtle)' : 'transparent', color: 'var(--content-primary)', display: 'flex', alignItems: 'center', gap: 8 }}
            >
              <Icon name="file-text" size={14} />
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{a.title}</span>
            </button>
          </li>
          ),
        )}
        {list.isPending ? <li style={{ color: 'var(--content-muted)', padding: 8 }}>Loading…</li> : null}
        {!list.isPending && items.length === 0 ? <li style={{ color: 'var(--content-muted)', padding: 8 }}>No files yet.</li> : null}
      </ul>

      {selected && current ? (
        <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', borderTop: '1px solid var(--glass-border)', marginTop: 8 }}>
          <div style={{ padding: '8px 10px 0' }}>
            <strong style={{ display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{current.title}</strong>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '6px 10px', flexWrap: 'wrap', fontSize: '0.8rem' }}>
            <button type="button" className="btn-ghost" onClick={() => setEditing((v) => !v)}>{editing ? 'Preview' : 'Edit'}</button>
            {dirty ? <button type="button" className="btn-primary" onClick={() => save.mutate(content)}>Save</button> : null}
            <button type="button" className="btn-ghost" onClick={() => setShowVersions(true)}>Versions</button>
            <a className="btn-ghost" href={artifactsApi.exportUrl(current.id, 'markdown', scope)} target="_blank" rel="noreferrer">MD</a>
            <a className="btn-ghost" href={artifactsApi.exportUrl(current.id, 'html', scope)} target="_blank" rel="noreferrer">HTML</a>
            <a className="btn-ghost" href={artifactsApi.exportUrl(current.id, 'pdf', scope)} target="_blank" rel="noreferrer">PDF</a>
            <button type="button" className="btn-ghost" aria-label="Delete file" onClick={() => setConfirmDelete(true)}><Icon name="trash" size={14} /></button>
          </div>
          <div style={{ flex: 1, minHeight: 0, overflow: 'auto', padding: '0 10px 10px' }}>
            {editing ? (
              <Suspense fallback={<div style={{ color: 'var(--content-muted)' }}>Loading editor…</div>}>
                <CodeEditor value={content} language={current.language} dark={isDark} onChange={setDraft} onSave={() => dirty && save.mutate(content)} />
              </Suspense>
            ) : previewKind(current.language) === 'markdown' ? (
              <Markdown text={content} className="message-content raw-text-content" />
            ) : previewKind(current.language) === 'html' ? (
              <iframe title={current.title} sandbox="" srcDoc={content} style={{ width: '100%', height: '60vh', border: 0, background: '#fff' }} />
            ) : (
              <pre className="font-mono" style={{ whiteSpace: 'pre-wrap', fontSize: '0.8rem' }}>{content}</pre>
            )}
          </div>
        </div>
      ) : null}

      {selected && current ? (
        <VersionsDialog open={showVersions} onClose={() => setShowVersions(false)} artifactId={current.id} scope={scope} onRestored={() => void queryClient.invalidateQueries({ queryKey: ['artifact', selected, key] })} />
      ) : null}

      <ConfirmDialog
        open={confirmDelete}
        title="Delete file?"
        message={`Delete "${current?.title ?? ''}" and its version history?`}
        confirmLabel="Delete"
        danger
        onCancel={() => setConfirmDelete(false)}
        onConfirm={() => {
          setConfirmDelete(false);
          if (selected) remove.mutate(selected);
        }}
      />
    </aside>
  );
}
