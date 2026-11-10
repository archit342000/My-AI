import { lazy, Suspense, useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '../../api/chats';
import { artifactsApi, artifactsKey, type Artifact, type ScopeRef } from '../../api/filesystem';
import { Icon } from '../../components/icons/Icon';
import { Button, IconButton } from '../../components/ui/Button';
import { EmptyState } from '../../components/ui/EmptyState';
import { ConfirmDialog } from '../../components/ui/ConfirmDialog';
import { Menu, type MenuEntry } from '../../components/ui/Menu';
import { SegmentedControl } from '../../components/ui/SegmentedControl';
import { showToast } from '../../components/ui/toast-store';
import { nextArtifactTitle } from '../../lib/artifact-names';
import { Markdown } from '../../components/markdown/Markdown';
import { useUiStore } from '../../state/ui-store';
import { previewKind } from './language';
import { VersionsDialog } from './VersionsDialog';
import { buildTree, isDirectoryEntry, type TreeNode } from './artifact-tree';

const CodeEditor = lazy(() => import('./CodeEditor').then((m) => ({ default: m.CodeEditor })));

const EXPORTS: Array<{ format: 'markdown' | 'html' | 'pdf'; label: string }> = [
  { format: 'markdown', label: 'Markdown (.md)' },
  { format: 'html', label: 'HTML (.html)' },
  { format: 'pdf', label: 'PDF (.pdf)' },
];

export interface ArtifactPanelProps {
  scope: ScopeRef;
  /** Shows a close button in the header. Omit when the panel is not an overlay. */
  onClose?: () => void;
}

/** Files panel for a chat or workspace: a folder tree, a preview/edit viewer, versions and export. */
export function ArtifactPanel({ scope, onClose }: ArtifactPanelProps) {
  const queryClient = useQueryClient();
  const themeMode = useUiStore((s) => s.themeMode);
  const isDark =
    themeMode === 'dark' ||
    (themeMode === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);
  const [selected, setSelected] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<string | null>(null);
  const [showVersions, setShowVersions] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [filter, setFilter] = useState('');
  const [collapsed, setCollapsed] = useState<Set<string>>(() => new Set());
  const [, key] = artifactsKey(scope);

  const list = useQuery({
    queryKey: artifactsKey(scope),
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
  }, [selected]);

  const needle = filter.trim().toLowerCase();
  const tree = useMemo(() => buildTree(list.data ?? []), [list.data]);
  const matches = useMemo(
    () =>
      (list.data ?? []).filter(
        (a) => !isDirectoryEntry(a) && a.title.toLowerCase().includes(needle),
      ),
    [list.data, needle],
  );

  const create = useMutation({
    mutationFn: () =>
      artifactsApi.create(scope, {
        title: nextArtifactTitle((list.data ?? []).map((a) => a.title)),
        content: '',
        language: 'markdown',
      }),
    onSuccess: async (res) => {
      await queryClient.invalidateQueries({ queryKey: artifactsKey(scope) });
      // A chat's own artifact counts as chat content, so the chat joins the sidebar list.
      if (scope.chatId) await queryClient.invalidateQueries({ queryKey: queryKeys.chats });
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
      setEditing(false);
      await queryClient.invalidateQueries({ queryKey: artifactsKey(scope) });
      if (scope.chatId) await queryClient.invalidateQueries({ queryKey: queryKeys.chats });
    },
    onError: (e) => showToast(e instanceof Error ? e.message : 'Delete failed', 'error'),
  });

  const current = detail.data;
  const content = draft ?? current?.content ?? '';
  const dirty = draft !== null && draft !== current?.content;

  function toggleFolder(path: string) {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  }

  function renderNodes(nodes: TreeNode[], depth: number) {
    return nodes.map((node) => {
      const indent = { paddingLeft: 8 + depth * 14 }; // dynamic-style
      if (node.kind === 'folder') {
        const open = !collapsed.has(node.path);
        return (
          <li key={`dir:${node.path}`}>
            <button
              type="button"
              className="artifact-tree__row artifact-tree__folder"
              aria-expanded={open}
              style={indent} // dynamic-style
              onClick={() => toggleFolder(node.path)}
            >
              <Icon name={open ? 'chevron-down' : 'chevron-right'} size={12} />
              <Icon name="folder" size={14} />
              <span className="artifact-tree__name">{node.name}</span>
            </button>
            {open ? <ul className="artifact-tree__children">{renderNodes(node.children, depth + 1)}</ul> : null}
          </li>
        );
      }
      const a = node.artifact;
      return (
        <li key={a.id}>
          <button
            type="button"
            className="artifact-tree__row artifact-item"
            aria-current={selected === a.id}
            style={indent} // dynamic-style
            title={node.path}
            onClick={() => {
                setEditing(false);
                setSelected(a.id);
              }}
          >
            <Icon name="file-text" size={14} />
            <span className="artifact-item__title">{node.name}</span>
          </button>
        </li>
      );
    });
  }

  const exportMenu: MenuEntry[] = EXPORTS.map(({ format, label }) => ({
    type: 'item',
    id: format,
    label,
    onSelect: () => {
      if (current) window.open(artifactsApi.exportUrl(current.id, format, scope), '_blank', 'noopener');
    },
  }));

  const kind = current ? previewKind(current.language) : 'code';

  return (
    <section className="artifact-panel" aria-label="Artifacts">
      <header className="artifact-panel__header">
        <h2 className="artifact-panel__title">Files</h2>
        {onClose ? <IconButton icon="close" label="Close files panel" onClick={onClose} /> : null}
      </header>

      <div className="artifact-panel__filter-row">
        <input
          className="artifact-panel__filter"
          aria-label="Filter files"
          placeholder="Filter files…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
        <IconButton
          icon="plus"
          label="New file"
          onClick={() => create.mutate()}
          disabled={create.isPending}
        />
      </div>

      <ul className={selected ? 'artifact-tree artifact-tree--compact' : 'artifact-tree'}>
        {needle
          ? matches.map((a: Artifact) => (
              <li key={a.id}>
                <button
                  type="button"
                  className="artifact-tree__row artifact-item"
                  aria-current={selected === a.id}
                  title={a.title}
                  onClick={() => {
                setEditing(false);
                setSelected(a.id);
              }}
                >
                  <Icon name="file-text" size={14} />
                  <span className="artifact-item__title">{a.title}</span>
                </button>
              </li>
            ))
          : renderNodes(tree, 0)}
        {list.isPending ? <li className="artifact-tree__status">Loading…</li> : null}
      </ul>
      {!list.isPending && (needle ? matches.length === 0 : tree.length === 0) ? (
        <EmptyState
          icon="folder"
          title={needle ? 'No matching files' : 'No files yet'}
          description={
            needle ? 'Clear the filter to see every file.' : 'Use + to create a note, draft or piece of code.'
          }
        />
      ) : null}

      {selected && current ? (
        <div className="artifact-viewer">
          <div className="artifact-viewer__head">
            <strong className="artifact-viewer__title" title={current.title}>
              {current.title}
            </strong>
            {dirty ? (
              <span
                className="artifact-viewer__dirty"
                role="img"
                aria-label="Unsaved changes"
                title="Unsaved changes"
              />
            ) : null}
          </div>

          <div className="artifact-viewer__toolbar">
            <SegmentedControl
              label="View mode"
              value={editing ? 'edit' : 'preview'}
              onChange={(v) => setEditing(v === 'edit')}
              options={[
                { value: 'preview', label: 'Preview' },
                { value: 'edit', label: 'Edit' },
              ]}
            />
            <Button size="sm" variant="ghost" onClick={() => setShowVersions(true)}>
              Versions
            </Button>
            <Menu
              label="Export"
              items={exportMenu}
              trigger={(props) => (
                <Button size="sm" variant="ghost" {...props}>
                  Export
                  <Icon name="chevron-down" size={12} />
                </Button>
              )}
            />
            <span className="artifact-viewer__spacer" />
            {dirty ? (
              <Button size="sm" variant="primary" loading={save.isPending} onClick={() => save.mutate(content)}>
                Save
              </Button>
            ) : null}
            <IconButton
              icon="trash"
              label="Delete file"
              tone="danger"
              onClick={() => setConfirmDelete(true)}
            />
          </div>

          <div className="artifact-viewer__body">
            {editing ? (
              <Suspense fallback={<div className="artifact-viewer__status">Loading editor…</div>}>
                <CodeEditor
                  value={content}
                  language={current.language}
                  dark={isDark}
                  onChange={setDraft}
                  onSave={() => dirty && save.mutate(content)}
                />
              </Suspense>
            ) : kind === 'markdown' ? (
              <Markdown text={content} className="message-content raw-text-content" />
            ) : kind === 'html' ? (
              <iframe title={current.title} sandbox="" srcDoc={content} className="artifact-viewer__frame" />
            ) : (
              <pre className="artifact-viewer__plain">{content}</pre>
            )}
          </div>
        </div>
      ) : null}

      {selected && current ? (
        <VersionsDialog
          open={showVersions}
          onClose={() => setShowVersions(false)}
          artifactId={current.id}
          scope={scope}
          onRestored={() =>
            void queryClient.invalidateQueries({ queryKey: ['artifact', selected, key] })
          }
        />
      ) : null}

      <ConfirmDialog
        open={confirmDelete}
        title="Delete file?"
        message={`Delete "${current?.title ?? ''}" and its version history? This cannot be undone.`}
        confirmLabel="Delete"
        danger
        onCancel={() => setConfirmDelete(false)}
        onConfirm={() => {
          setConfirmDelete(false);
          if (selected) remove.mutate(selected);
        }}
      />
    </section>
  );
}
