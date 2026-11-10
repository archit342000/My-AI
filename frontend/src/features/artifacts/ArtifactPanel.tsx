import { lazy, Suspense, useEffect, useMemo, useRef, useState } from 'react';
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '../../api/chats';
import { artifactsApi, type Artifact, type ScopeRef } from '../../api/filesystem';
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
import { PromptDialog } from '../../components/ui/PromptDialog';
import { artifactPath, buildTree, folderPaths, isDirectoryEntry, parentFolder, type TreeNode } from './artifact-tree';
import { MoveFileDialog } from './MoveFileDialog';

const CodeEditor = lazy(() => import('./CodeEditor').then((m) => ({ default: m.CodeEditor })));

const scopeKey = (s: ScopeRef) => `${s.chatId ?? ''}|${s.workspaceId ?? ''}`;

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
    // The file on screen stays until the next one has arrived (no flash of an empty viewer).
    placeholderData: keepPreviousData,
  });
  const treeRef = useRef<HTMLUListElement>(null);
  const [renaming, setRenaming] = useState(false);
  const [moving, setMoving] = useState(false);
  const [newFolder, setNewFolder] = useState(false);
  /** Where the folder context menu is open, and the folder awaiting a delete confirmation. */
  const [folderMenu, setFolderMenu] = useState<{ path: string; x: number; y: number } | null>(null);
  const [deletingFolder, setDeletingFolder] = useState<string | null>(null);
  /** An action that would drop the unsaved draft, held until the user confirms. */
  const [pendingDiscard, setPendingDiscard] = useState<(() => void) | null>(null);

  useEffect(() => {
    setDraft(null);
  }, [selected]);

  // A selected file inside a collapsed folder (just moved there, say) opens the folders above it.
  useEffect(() => {
    const entry = (list.data ?? []).find((a) => a.id === selected);
    if (!entry) return;
    const parts = artifactPath(entry).split('/').slice(0, -1);
    const ancestors = parts.map((_, i) => parts.slice(0, i + 1).join('/'));
    setCollapsed((prev) => (ancestors.some((p) => prev.has(p)) ? new Set([...prev].filter((p) => !ancestors.includes(p))) : prev));
  }, [selected, list.data]);

  // The tree scrolls inside a bounded box: keep the selected row in view.
  useEffect(() => {
    treeRef.current?.querySelector('[aria-current="true"]')?.scrollIntoView?.({ block: 'nearest' });
  }, [selected, list.data]);

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
      await queryClient.invalidateQueries({ queryKey: ['artifacts', key] });
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
      // Reload first, then drop the draft: clearing it while the old content is still loaded would hand the editor
      // the stale text, which it reports back as a new draft (the file then looks unsaved).
      await queryClient.invalidateQueries({ queryKey: ['artifact', selected, key] });
      setDraft(null);
    },
    onError: (e) => showToast(e instanceof Error ? e.message : 'Save failed', 'error'),
  });

  const remove = useMutation({
    mutationFn: (id: string) => artifactsApi.remove(id, scope),
    onSuccess: async () => {
      setSelected(null);
      setEditing(false);
      await queryClient.invalidateQueries({ queryKey: ['artifacts', key] });
      if (scope.chatId) await queryClient.invalidateQueries({ queryKey: queryKeys.chats });
    },
    onError: (e) => showToast(e instanceof Error ? e.message : 'Delete failed', 'error'),
  });

  const refreshFiles = async () => {
    await queryClient.invalidateQueries({ queryKey: ['artifacts', key] });
    if (selected) await queryClient.invalidateQueries({ queryKey: ['artifact', selected, key] });
  };

  // Rename and move are updates of the file's title and folder (a file read from disk cannot be renamed or moved).
  const rename = useMutation({
    mutationFn: (title: string) => artifactsApi.update(selected as string, scope, { title }),
    onSuccess: async () => {
      setRenaming(false);
      await refreshFiles();
    },
    onError: (e) => showToast(e instanceof Error ? e.message : 'Rename failed', 'error'),
  });
  const move = useMutation({
    mutationFn: (folder: string) => artifactsApi.update(selected as string, scope, { folder }),
    onSuccess: async () => {
      setMoving(false);
      await refreshFiles();
    },
    onError: (e) => showToast(e instanceof Error ? e.message : 'Move failed', 'error'),
  });
  const createFolder = useMutation({
    mutationFn: (path: string) => artifactsApi.createDirectory(scope, path),
    onSuccess: refreshFiles,
    onError: (e) => showToast(e instanceof Error ? e.message : 'Could not create the folder', 'error'),
  });
  const removeFolder = useMutation({
    mutationFn: (path: string) => artifactsApi.deleteDirectory(scope, path),
    onSuccess: refreshFiles,
    // The server only removes an empty folder and says so in its own words.
    onError: (e) => showToast(e instanceof Error ? e.message : 'Could not delete the folder', 'error'),
  });

  const current = detail.data;
  const content = draft ?? current?.content ?? '';
  const dirty = draft !== null && draft !== current?.content;
  /** True while the file on screen is the previous one, waiting for the selected one. */
  const loadingNext = detail.isPlaceholderData;

  // Whatever closes the panel from outside (the header button) asks first when this is set.
  const setArtifactsDirty = useUiStore((st) => st.setArtifactsDirty);
  useEffect(() => {
    setArtifactsDirty(dirty);
    return () => setArtifactsDirty(false);
  }, [dirty, setArtifactsDirty]);

  /** Runs `action`, after asking first when it would drop unsaved edits. */
  function confirmDiscard(action: () => void) {
    if (dirty) setPendingDiscard(() => action);
    else action();
  }

  const isDisk = Boolean(current?.id.startsWith('disk:'));
  // Where the file is comes from the list entry (it carries the folder); the single-file read may not.
  const entry = (list.data ?? []).find((a) => a.id === current?.id);
  const currentPath = entry ? artifactPath(entry) : (current?.title ?? '');

  function download() {
    if (!current) return;
    const link = document.createElement('a');
    link.href = artifactsApi.rawUrl(current.id, scope);
    link.download = current.title;
    link.click();
  }

  async function copyContents() {
    if (!navigator.clipboard) {
      showToast('Copying needs a secure (https) connection', 'error');
      return;
    }
    try {
      await navigator.clipboard.writeText(content);
      showToast('Copied', 'success');
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Copy failed', 'error');
    }
  }

  const moreMenu: MenuEntry[] = [
    { id: 'rename', label: 'Rename', icon: 'edit', disabled: isDisk, onSelect: () => setRenaming(true) },
    { id: 'move', label: 'Move to folder…', icon: 'folder', disabled: isDisk, onSelect: () => setMoving(true) },
    { type: 'separator', id: 'more-sep' },
    { id: 'download', label: 'Download', onSelect: download },
    { id: 'copy', label: 'Copy contents', icon: 'copy', onSelect: () => void copyContents() },
  ];

  function selectFile(id: string) {
    if (id === selected) return;
    confirmDiscard(() => {
      setEditing(false);
      setSelected(id);
    });
  }
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
              onContextMenu={(e) => {
                e.preventDefault();
                // From the keyboard (Shift+F10) the event carries no position: open at the row.
                const box = e.currentTarget.getBoundingClientRect();
                const atRow = e.clientX === 0 && e.clientY === 0;
                setFolderMenu({ path: node.path, x: atRow ? box.left + 24 : e.clientX, y: atRow ? box.bottom : e.clientY });
              }}
              onKeyDown={(e) => {
                if (e.key === 'Delete') setDeletingFolder(node.path);
              }}
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
            onClick={() => selectFile(a.id)}
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
        {onClose ? (
          <IconButton icon="close" label="Close files panel" onClick={() => confirmDiscard(onClose)} />
        ) : null}
      </header>

      <div className="artifact-panel__filter-row">
        <input
          className="artifact-panel__filter"
          aria-label="Filter files"
          placeholder="Filter files…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
        <IconButton icon="folder" label="New folder" onClick={() => setNewFolder(true)} />
        <IconButton
          icon="plus"
          label="New file"
          onClick={() => confirmDiscard(() => create.mutate())}
          disabled={create.isPending}
        />
      </div>

      <ul ref={treeRef} className={selected ? 'artifact-tree artifact-tree--compact' : 'artifact-tree'}>
        {needle
          ? matches.map((a: Artifact) => (
              <li key={a.id}>
                <button
                  type="button"
                  className="artifact-tree__row artifact-item"
                  aria-current={selected === a.id}
                  title={a.title}
                  onClick={() => selectFile(a.id)}
                >
                  <Icon name="file-text" size={14} />
                  <span className="artifact-item__title">{a.title}</span>
                </button>
              </li>
            ))
          : renderNodes(tree, 0)}
        {list.isPending ? <li className="artifact-tree__status">Loading…</li> : null}
      </ul>
      {list.isError ? (
        <p className="artifact-panel__error" role="alert">
          {list.error instanceof Error ? list.error.message : 'Could not load the files'}
        </p>
      ) : null}
      {detail.isError ? (
        <p className="artifact-panel__error" role="alert">
          {detail.error instanceof Error ? detail.error.message : 'Could not open the file'}
        </p>
      ) : null}
      {!list.isPending && !list.isError && (needle ? matches.length === 0 : tree.length === 0) ? (
        <EmptyState
          icon="folder"
          title={needle ? 'No matching files' : 'No files yet'}
          description={
            needle ? 'Clear the filter to see every file.' : 'Use + to create a note, draft or piece of code.'
          }
        />
      ) : null}

      {selected && current ? (
        <div className={loadingNext ? 'artifact-viewer artifact-viewer--loading' : 'artifact-viewer'} aria-busy={loadingNext}>
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
            {/* Every version endpoint needs a chat: a file opened in a workspace has no history here. */}
            {scope.chatId ? (
              <Button size="sm" variant="ghost" onClick={() => confirmDiscard(() => setShowVersions(true))}>
                Versions
              </Button>
            ) : null}
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
            <Menu
              label="More file actions"
              items={moreMenu}
              trigger={(props) => (
                <IconButton icon="menu" label="More file actions" {...props} />
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

      {selected && current && scope.chatId ? (
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

      <PromptDialog
        open={renaming}
        title="Rename file"
        message="Enter a new name for the file:"
        initialValue={current?.title ?? ''}
        confirmLabel="Rename"
        onCancel={() => setRenaming(false)}
        onSubmit={(value) => {
          const name = value.trim();
          if (!name || name === current?.title) setRenaming(false);
          else if (name.includes('/')) {
            // A slash would move the file: that is what Move is for.
            setRenaming(false);
            showToast('A file name cannot contain "/". Use Move to change its folder.', 'error');
          } else rename.mutate(name);
        }}
      />
      <MoveFileDialog
        key={`${current?.id}:${moving}`}
        open={moving}
        fileName={current?.title ?? ''}
        currentFolder={parentFolder(currentPath)}
        folders={folderPaths(tree)}
        onMove={(folder) => move.mutate(folder)}
        onCancel={() => setMoving(false)}
      />
      <PromptDialog
        open={newFolder}
        title="New folder"
        message="Enter the folder path (use / for a folder inside another):"
        confirmLabel="Create"
        onCancel={() => setNewFolder(false)}
        onSubmit={(value) => {
          setNewFolder(false);
          const path = value.trim().replace(/^\/+|\/+$/g, '');
          if (path) createFolder.mutate(path);
        }}
      />
      <Menu
        label="Folder actions"
        point={folderMenu ? { x: folderMenu.x, y: folderMenu.y } : null}
        items={[
          {
            id: 'delete-folder',
            label: 'Delete folder',
            icon: 'trash',
            danger: true,
            onSelect: () => setDeletingFolder(folderMenu?.path ?? null),
          },
        ]}
        onClose={() => setFolderMenu(null)}
      />
      <ConfirmDialog
        open={deletingFolder !== null}
        title="Delete folder?"
        message={`Delete the folder "${deletingFolder ?? ''}"? Only an empty folder can be deleted.`}
        confirmLabel="Delete"
        danger
        onCancel={() => setDeletingFolder(null)}
        onConfirm={() => {
          const path = deletingFolder;
          setDeletingFolder(null);
          if (path) removeFolder.mutate(path);
        }}
      />

      <ConfirmDialog
        open={pendingDiscard !== null}
        title="Discard unsaved changes?"
        message="This file has changes that are not saved. Continuing drops them."
        confirmLabel="Discard"
        danger
        onCancel={() => setPendingDiscard(null)}
        onConfirm={() => {
          const action = pendingDiscard;
          setPendingDiscard(null);
          setDraft(null);
          action?.();
        }}
      />

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
