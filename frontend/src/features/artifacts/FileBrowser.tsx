import {
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
  type MouseEvent as ReactMouseEvent,
  type Ref,
} from 'react';
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '../../api/chats';
import {
  artifactsApi,
  artifactsKey,
  codeExecApi,
  type Artifact,
  type ScopeRef,
} from '../../api/filesystem';
import { clarificationApi } from '../../api/tools';
import { Markdown } from '../../components/markdown/Markdown';
import { Button, IconButton } from '../../components/ui/Button';
import { ConfirmDialog } from '../../components/ui/ConfirmDialog';
import { EmptyState } from '../../components/ui/EmptyState';
import { Field, Textarea } from '../../components/ui/Field';
import { Menu, type MenuEntry } from '../../components/ui/Menu';
import { Notice } from '../../components/ui/Notice';
import { showToast } from '../../components/ui/toast-store';
import { nextArtifactTitle } from '../../lib/artifact-names';
import { useStreamStore } from '../../state/stream-store';
import { useUiStore } from '../../state/ui-store';
import {
  artifactPath,
  buildTree,
  folderPaths,
  isRunnable,
  languageForName,
  parentFolder,
  type TreeNode,
} from './artifact-tree';
import type { CodeEditorHandle } from './CodeEditor';
import { EditorToolbar, type EditorMode } from './EditorToolbar';
import { FilePlacePopup } from './FilePlacePopup';
import { searchFiles } from './file-search';
import { FileSearchBox, FileSearchResults } from './FileSearch';
import { FileTree, type RowMenuRequest } from './FileTree';
import { previewKind } from './language';
import { RunOutput, type RunResult } from './RunOutput';
import { toggleTask } from './task-list';
import { useAutoSave } from './useAutoSave';
import { VersionsDialog } from './VersionsDialog';

const CodeEditor = lazy(() => import('./CodeEditor').then((m) => ({ default: m.CodeEditor })));

const EXPORTS: Array<{ format: 'markdown' | 'html' | 'pdf'; label: string }> = [
  { format: 'markdown', label: 'Markdown (.md)' },
  { format: 'html', label: 'HTML (.html)' },
  { format: 'pdf', label: 'PDF (.pdf)' },
];

/** The type the research agent gives a plan that waits for a go-ahead (backend research agent). */
const PLAN_PENDING = 'research_plan_pending';

export interface FileBrowserHandle {
  /** Saves anything still unsaved. Resolves false when it could not be saved. */
  flush: () => Promise<boolean>;
}

export interface FileBrowserProps {
  ref?: Ref<FileBrowserHandle>;
  scope: ScopeRef;
  full: boolean;
  onToggleFull: () => void;
}

/** What the where-and-name pop-up is doing. */
type Place =
  | { kind: 'new-file'; name: string; folder: string }
  | { kind: 'new-folder'; name: string; folder: string }
  | { kind: 'rename'; id: string; name: string; folder: string };

const PLACE_TEXT: Record<Place['kind'], { title: string; nameLabel: string; confirm: string }> = {
  'new-file': { title: 'New file', nameLabel: 'File name', confirm: 'Create file' },
  'new-folder': { title: 'New folder', nameLabel: 'Folder name', confirm: 'Create folder' },
  rename: { title: 'Rename or move', nameLabel: 'File name', confirm: 'Save' },
};

function message(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback;
}

/**
 * The file browser: the list (folders, search) and the editor for one file. Used in the Files panel
 * beside a chat, in a workspace and full screen. Edits save by themselves; anything unsaved is saved
 * before another file opens or the browser goes away.
 */
export function FileBrowser({ ref, scope, full, onToggleFull }: FileBrowserProps) {
  const queryClient = useQueryClient();
  const [, key] = artifactsKey(scope);
  const root = useRef<HTMLDivElement>(null);
  const editor = useRef<CodeEditorHandle>(null);
  const newButton = useRef<HTMLButtonElement>(null);
  const moreButton = useRef<HTMLButtonElement | null>(null);
  const placeAnchor = useRef<HTMLElement | null>(null);

  const [selected, setSelected] = useState<string | null>(null);
  const [draft, setDraft] = useState<{ id: string; text: string } | null>(null);
  const [modeFor, setModeFor] = useState<{ id: string; mode: EditorMode } | null>(null);
  const [history, setHistory] = useState({ undo: false, redo: false });
  const [filter, setFilter] = useState('');
  const [collapsed, setCollapsed] = useState<Set<string>>(() => new Set());
  const [rowMenu, setRowMenu] = useState<RowMenuRequest | null>(null);
  const [place, setPlace] = useState<Place | null>(null);
  const [deleting, setDeleting] = useState<{ id: string; title: string } | null>(null);
  const [deletingFolder, setDeletingFolder] = useState<string | null>(null);
  const [showVersions, setShowVersions] = useState(false);
  const [run, setRun] = useState<RunResult | null>(null);
  const [suggesting, setSuggesting] = useState(false);
  const [suggestion, setSuggestion] = useState('');
  const [answering, setAnswering] = useState(false);

  const list = useQuery({
    queryKey: artifactsKey(scope),
    queryFn: () => artifactsApi.list(scope),
    enabled: Boolean(scope.chatId || scope.workspaceId),
  });
  const detail = useQuery({
    queryKey: ['artifact', selected, key],
    queryFn: () => artifactsApi.get(selected as string, scope),
    enabled: Boolean(selected),
    // The file on screen stays until the next one has arrived (no flash of an empty editor).
    placeholderData: keepPreviousData,
  });
  const current = selected ? detail.data : undefined;
  const isDisk = Boolean(current?.id.startsWith('disk:'));
  const version = useQuery({
    queryKey: ['artifact-version', current?.id, key],
    queryFn: () => artifactsApi.currentVersion(current?.id as string, scope),
    // Every version endpoint needs a chat: a file opened in a workspace has no history here.
    enabled: Boolean(current && scope.chatId && !isDisk),
  });

  const saveFile = useCallback(
    async (id: string, content: string) => {
      await artifactsApi.update(id, scope, { content });
      // The saved text is now what the server has: no reload, so nothing typed since is replaced.
      queryClient.setQueryData<Artifact & { content: string }>(['artifact', id, key], (old) =>
        old ? { ...old, content } : old,
      );
      void queryClient.invalidateQueries({ queryKey: ['artifact-version', id, key] });
    },
    // The scope is identified by its key.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [queryClient, key],
  );
  const auto = useAutoSave(saveFile);
  useImperativeHandle(ref, () => ({ flush: auto.flush }), [auto.flush]);

  /** Saves what is unsaved; says so and returns false when that fails (the file then stays open). */
  async function saved(): Promise<boolean> {
    if (await auto.flush()) return true;
    showToast('Could not save your changes, so this file stays open', 'error');
    return false;
  }

  async function openFile(id: string | null) {
    if (id === selected) return;
    if (!(await saved())) return;
    setRun(null);
    setSuggesting(false);
    setSelected(id);
  }

  // A selected file inside a collapsed folder (just moved there, say) opens the folders above it.
  useEffect(() => {
    const entry = (list.data ?? []).find((a) => a.id === selected);
    if (!entry) return;
    const parts = artifactPath(entry).split('/').slice(0, -1);
    const ancestors = parts.map((_, i) => parts.slice(0, i + 1).join('/'));
    setCollapsed((prev) =>
      ancestors.some((p) => prev.has(p))
        ? new Set([...prev].filter((p) => !ancestors.includes(p)))
        : prev,
    );
  }, [selected, list.data]);

  // The list scrolls inside a bounded box: keep the selected row in view.
  useEffect(() => {
    root.current?.querySelector('[aria-current="true"]')?.scrollIntoView?.({ block: 'nearest' });
  }, [selected, list.data]);

  // A file link in the transcript asks for a file: select it once the list is in.
  const requestedPath = useUiStore((s) => s.requestedArtifactPath);
  useEffect(() => {
    // Read the store, not the closure: a second run of this effect (StrictMode) must not answer the
    // same request again.
    if (!requestedPath || useUiStore.getState().requestedArtifactPath === null) return;
    if (list.isError && !list.data) {
      useUiStore.getState().clearRequestedArtifact();
      showToast('Could not load files', 'error');
      return;
    }
    // Wait while the list is refetching: a panel opened on a cached list may not have the new file yet.
    if (!list.data || list.isFetching) return;
    const wanted = requestedPath.replace(/^\.?\//, '');
    const hit = list.data.find(
      (a) =>
        a.title === wanted ||
        a.filename === wanted ||
        (a.folder ? `${a.folder}/${a.filename}` === wanted : false),
    );
    // Clear first: the check above then stops any second run from answering the request again.
    useUiStore.getState().clearRequestedArtifact();
    if (hit) void openFile(hit.id);
    else showToast(`File not found: ${requestedPath}`, 'error');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [requestedPath, list.data, list.isFetching, list.isError]);

  const items = useMemo(() => list.data ?? [], [list.data]);
  const tree = useMemo(
    () => buildTree(items, { hidePlaceholder: Boolean(scope.workspaceId) }),
    [items, scope.workspaceId],
  );
  const folders = useMemo(() => folderPaths(tree), [tree]);
  const needle = filter.trim();
  const hits = useMemo(() => {
    if (!needle) return [];
    // Text is searched in the files opened so far (their contents are in the cache).
    const contents = new Map<string, string>();
    for (const a of items) {
      const cached = queryClient.getQueryData<{ content?: string }>(['artifact', a.id, key]);
      if (typeof cached?.content === 'string') contents.set(a.id, cached.content);
    }
    return searchFiles(items, contents, needle);
    // `detail.data` is listed so a file that has just loaded is searched too.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [items, needle, key, queryClient, detail.data]);

  const refreshList = async () => {
    await queryClient.invalidateQueries({ queryKey: artifactsKey(scope) });
    // A chat's own file counts as chat content, so the chat joins the sidebar list.
    if (scope.chatId) await queryClient.invalidateQueries({ queryKey: queryKeys.chats });
  };

  const create = useMutation({
    mutationFn: ({ name, folder }: { name: string; folder: string }) =>
      artifactsApi.create(scope, {
        title: name,
        content: '',
        language: languageForName(name),
        ...(folder ? { folder } : {}),
      }),
    onSuccess: async (res) => {
      await refreshList();
      setModeFor({ id: res.id, mode: 'code' });
      setRun(null);
      setSelected(res.id);
    },
    onError: (e) => showToast(message(e, 'Could not create the file'), 'error'),
  });
  const remove = useMutation({
    mutationFn: (id: string) => artifactsApi.remove(id, scope),
    onSuccess: async (_res, id) => {
      if (id === selected) setSelected(null);
      await refreshList();
    },
    onError: (e) => showToast(message(e, 'Could not delete the file'), 'error'),
  });
  // Rename and move are updates of the file's title and folder (a file read from disk cannot be renamed or moved).
  const relocate = useMutation({
    mutationFn: ({ id, body }: { id: string; body: { title?: string; folder?: string } }) =>
      artifactsApi.update(id, scope, body),
    onSuccess: async (_res, { id }) => {
      await queryClient.invalidateQueries({ queryKey: ['artifacts', key] });
      await queryClient.invalidateQueries({ queryKey: ['artifact', id, key] });
    },
    onError: (e) => showToast(message(e, 'Could not rename or move the file'), 'error'),
  });
  const createFolder = useMutation({
    mutationFn: (path: string) => artifactsApi.createDirectory(scope, path),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['artifacts', key] }),
    onError: (e) => showToast(message(e, 'Could not create the folder'), 'error'),
  });
  const removeFolder = useMutation({
    mutationFn: (path: string) => artifactsApi.deleteDirectory(scope, path),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['artifacts', key] }),
    // The server only removes an empty folder and says so in its own words.
    onError: (e) => showToast(message(e, 'Could not delete the folder'), 'error'),
  });

  // Where the file is comes from the list entry (it carries the folder); the single-file read may not.
  const entry = items.find((a) => a.id === current?.id);
  const currentPath = entry ? artifactPath(entry) : (current?.title ?? '');
  const content = current ? (draft?.id === current.id ? draft.text : current.content) : '';
  const kind = current ? previewKind(current.language) : 'code';
  const mode: EditorMode | null =
    kind === 'code' ? null : modeFor?.id === current?.id && modeFor ? modeFor.mode : 'preview';
  const showEditor = mode !== 'preview';
  /** True while the file on screen is the previous one, waiting for the selected one. */
  const loadingNext = detail.isPlaceholderData;

  /** Takes new text for the open file: it is shown at once and saved after a pause. */
  function edit(text: string) {
    if (!current) return;
    // The editor reports the text it was just given: that is not a change.
    if (draft?.id !== current.id && text === current.content) return;
    setDraft({ id: current.id, text });
    auto.schedule(current.id, text);
  }

  useEffect(() => {
    if (!showEditor) setHistory({ undo: false, redo: false });
  }, [showEditor, current?.id]);

  function download(id: string, title: string) {
    const link = document.createElement('a');
    link.href = artifactsApi.rawUrl(id, scope);
    link.download = title;
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
      showToast(message(err, 'Could not copy'), 'error');
    }
  }

  function runBlocked(path: string): string | null {
    if (!scope.chatId) return 'A file can be run from the Files panel of a chat';
    if (!isRunnable(path)) return 'This kind of file cannot be run';
    return null;
  }

  async function runFile(path: string) {
    if (!scope.chatId || !(await saved())) return;
    setRun({ state: 'running', text: '' });
    try {
      const text = await codeExecApi.runFile(scope.chatId, path);
      setRun({ state: text.startsWith('Error:') ? 'failed' : 'done', text });
    } catch (err) {
      setRun({ state: 'failed', text: message(err, 'The file could not be run.') });
    }
  }

  function openPlace(next: Place, anchor: HTMLElement | null) {
    placeAnchor.current = anchor ?? newButton.current;
    setPlace(next);
  }

  /** The More button of a row, which the where-and-name pop-up hangs from. */
  function rowAnchor(node: TreeNode): HTMLElement | null {
    const id = node.kind === 'file' ? node.artifact.id : `dir:${node.path}`;
    return root.current?.querySelector<HTMLElement>(`[data-node="${CSS.escape(id)}"]`) ?? null;
  }

  function renameEntry(a: Artifact, anchor: HTMLElement | null) {
    openPlace(
      {
        kind: 'rename',
        id: a.id,
        name: a.title.split('/').pop() ?? a.title,
        folder: parentFolder(artifactPath(a)),
      },
      anchor,
    );
  }

  function submitPlace(name: string, folder: string) {
    const what = place;
    setPlace(null);
    if (!what) return;
    if (what.kind === 'new-folder') createFolder.mutate(folder ? `${folder}/${name}` : name);
    else if (what.kind === 'new-file')
      void saved().then((ok) => ok && create.mutate({ name, folder }));
    else {
      const body: { title?: string; folder?: string } = {};
      if (name !== what.name) body.title = name;
      if (folder !== what.folder) body.folder = folder;
      if (body.title !== undefined || body.folder !== undefined)
        relocate.mutate({ id: what.id, body });
    }
  }

  function toggleFolder(path: string) {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  }

  function fileItems(
    a: Artifact,
    path: string,
    anchor: () => HTMLElement | null,
    inToolbar: boolean,
  ): MenuEntry[] {
    const disk = a.id.startsWith('disk:');
    const blocked = runBlocked(path);
    const rename: MenuEntry = {
      id: 'rename',
      label: 'Rename or move…',
      icon: 'edit',
      disabled: disk,
      reason: disk ? 'Kept on disk' : undefined,
      onSelect: () => renameEntry(a, anchor()),
    };
    const downloadItem: MenuEntry = {
      id: 'download',
      label: 'Download',
      icon: 'download',
      onSelect: () => download(a.id, a.title),
    };
    const remove: MenuEntry = {
      id: 'delete',
      label: 'Delete',
      icon: 'trash',
      danger: true,
      onSelect: () => setDeleting({ id: a.id, title: a.title }),
    };
    if (inToolbar) {
      return [
        rename,
        downloadItem,
        {
          type: 'submenu',
          id: 'export',
          label: 'Export as',
          items: EXPORTS.map(({ format, label }) => ({
            id: format,
            label,
            onSelect: () =>
              window.open(artifactsApi.exportUrl(a.id, format, scope), '_blank', 'noopener'),
          })),
        },
        { type: 'separator', id: 'sep' },
        remove,
      ];
    }
    return [
      { id: 'open', label: 'Open', icon: 'file-text', onSelect: () => void openFile(a.id) },
      {
        id: 'run',
        label: 'Run',
        icon: 'play',
        disabled: blocked !== null,
        onSelect: () => void openFile(a.id).then(() => runFile(path)),
      },
      downloadItem,
      rename,
      { type: 'separator', id: 'sep' },
      remove,
    ];
  }

  function folderItems(node: TreeNode): MenuEntry[] {
    return [
      {
        id: 'new-file-here',
        label: 'New file here',
        icon: 'file-text',
        onSelect: () =>
          openPlace(
            {
              kind: 'new-file',
              name: nextArtifactTitle(items.map((a) => a.title)),
              folder: node.path,
            },
            rowAnchor(node),
          ),
      },
      {
        id: 'new-folder-here',
        label: 'New folder here',
        icon: 'folder',
        onSelect: () =>
          openPlace({ kind: 'new-folder', name: '', folder: node.path }, rowAnchor(node)),
      },
      { type: 'separator', id: 'sep' },
      {
        id: 'delete-folder',
        label: 'Delete folder',
        icon: 'trash',
        danger: true,
        onSelect: () => setDeletingFolder(node.path),
      },
    ];
  }

  const rowItems: MenuEntry[] = !rowMenu
    ? []
    : rowMenu.node.kind === 'folder'
      ? folderItems(rowMenu.node)
      : fileItems(rowMenu.node.artifact, rowMenu.node.path, () => rowAnchor(rowMenu.node), false);

  // The research agent's plan waits for a go-ahead: it is given here, beside the plan itself.
  const pending = useStreamStore((s) =>
    scope.chatId && s.chatId === scope.chatId ? (s.live?.pendingRequest ?? null) : null,
  );
  const planAsk = pending && entry?.file_system_type === PLAN_PENDING ? pending : null;

  async function answerPlan(text: string) {
    if (!planAsk || !scope.chatId || !text) return;
    setAnswering(true);
    try {
      await clarificationApi.respond(scope.chatId, planAsk.id, text);
      setSuggesting(false);
      setSuggestion('');
    } catch (err) {
      showToast(message(err, 'Could not send the answer'), 'error');
    } finally {
      setAnswering(false);
    }
  }

  /** A tick box pressed in the preview ticks the same box in the file's text. */
  function onPreviewClick(event: ReactMouseEvent<HTMLDivElement>) {
    const box = event.target;
    if (!(box instanceof HTMLInputElement) || box.type !== 'checkbox') return;
    const boxes = Array.from(event.currentTarget.querySelectorAll('input[type="checkbox"]'));
    edit(toggleTask(content, boxes.indexOf(box)));
  }
  const preview = useRef<HTMLDivElement>(null);
  useEffect(() => {
    // The renderer writes tick boxes switched off (they are for reading in a chat): here they work.
    preview.current?.querySelectorAll<HTMLInputElement>('input[type="checkbox"]').forEach((box) => {
      box.disabled = false;
    });
  });

  const empty =
    !list.isPending && !list.isError && (needle ? hits.length === 0 : tree.length === 0);

  return (
    <div ref={root} className="fb" data-view={selected ? 'edit' : 'list'}>
      <div className="fb-list">
        <div className="fb-tools">
          <FileSearchBox value={filter} onChange={setFilter} />
          <Menu
            label="New"
            items={[
              {
                id: 'new-file',
                label: 'New file',
                icon: 'file-text',
                onSelect: () =>
                  openPlace(
                    {
                      kind: 'new-file',
                      name: nextArtifactTitle(items.map((a) => a.title)),
                      folder: '',
                    },
                    newButton.current,
                  ),
              },
              {
                id: 'new-folder',
                label: 'New folder',
                icon: 'folder',
                onSelect: () =>
                  openPlace({ kind: 'new-folder', name: '', folder: '' }, newButton.current),
              },
            ]}
            trigger={(props) => (
              <IconButton
                icon="plus"
                className="fb-new"
                label="New file or folder"
                {...props}
                ref={(el) => {
                  props.ref.current = el;
                  newButton.current = el;
                }}
              />
            )}
          />
        </div>

        {needle ? (
          <FileSearchResults hits={hits} selected={selected} onOpen={(id) => void openFile(id)} />
        ) : (
          <FileTree
            nodes={tree}
            selected={selected}
            collapsed={collapsed}
            onToggleFolder={toggleFolder}
            onOpenFile={(id) => void openFile(id)}
            onMenu={setRowMenu}
            onDeleteKey={(node) =>
              node.kind === 'folder'
                ? setDeletingFolder(node.path)
                : setDeleting({ id: node.artifact.id, title: node.artifact.title })
            }
          />
        )}
        {list.isPending ? (
          <p className="fb-status" role="status">
            Loading the files
          </p>
        ) : null}
        {list.isError ? (
          <Notice tone="bad" actionLabel="Try again" onAction={() => void list.refetch()}>
            {message(list.error, 'Could not load the files')}
          </Notice>
        ) : null}
        {empty ? (
          <EmptyState
            icon="folder"
            title={needle ? 'Nothing matches' : 'No files yet'}
            description={
              needle
                ? 'Names are searched in every file; text only in the files you have opened.'
                : 'Use + to start a note, a draft or a piece of code.'
            }
          />
        ) : null}
      </div>

      <div className="fb-edit" aria-busy={loadingNext || undefined}>
        {detail.isError && !current ? (
          <Notice tone="bad" actionLabel="Try again" onAction={() => void detail.refetch()}>
            {message(detail.error, 'Could not open the file')}
          </Notice>
        ) : null}
        {current ? (
          <>
            <EditorToolbar
              path={currentPath}
              language={current.language}
              version={typeof version.data === 'number' ? version.data : null}
              saveState={auto.state}
              onBack={() => void openFile(null)}
              mode={mode}
              onMode={(next) => setModeFor({ id: current.id, mode: next })}
              canUndo={history.undo}
              canRedo={history.redo}
              onUndo={() => editor.current?.undo()}
              onRedo={() => editor.current?.redo()}
              onCopy={() => void copyContents()}
              runBlocked={runBlocked(currentPath)}
              running={run?.state === 'running'}
              onRun={() => void runFile(currentPath)}
              versionsBlocked={scope.chatId ? null : 'Version history is kept for files in a chat'}
              onVersions={() => void saved().then((ok) => ok && setShowVersions(true))}
              full={full}
              onToggleFull={onToggleFull}
              moreItems={fileItems(entry ?? current, currentPath, () => moreButton.current, true)}
              moreRef={(el) => {
                moreButton.current = el;
              }}
            />
            {auto.state === 'error' ? (
              <Notice tone="bad" actionLabel="Try again" onAction={() => void auto.flush()}>
                This file could not be saved. Your changes are still here.
              </Notice>
            ) : null}
            {planAsk && !suggesting ? (
              <div className="ui-notice fb-plan" role="status">
                <span className="ui-notice__light" aria-hidden="true" />
                <div className="ui-notice__text">This plan waits for your go-ahead.</div>
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={answering}
                  onClick={() => setSuggesting(true)}
                >
                  Suggest changes
                </Button>
                <Button
                  size="sm"
                  variant="primary"
                  loading={answering}
                  onClick={() => void answerPlan(planAsk.options[0] ?? 'Yes, proceed')}
                >
                  Approve
                </Button>
              </div>
            ) : null}
            {planAsk && suggesting ? (
              <form
                className="fb-suggest"
                onSubmit={(e) => {
                  e.preventDefault();
                  void answerPlan(suggestion.trim());
                }}
              >
                <Field label="What should change?">
                  {(c) => (
                    <Textarea
                      {...c}
                      rows={3}
                      value={suggestion}
                      placeholder="For example: compare three tools instead of two"
                      onChange={(e) => setSuggestion(e.target.value)}
                    />
                  )}
                </Field>
                <div className="fb-suggest__buttons">
                  <Button variant="ghost" onClick={() => setSuggesting(false)}>
                    Cancel
                  </Button>
                  <Button
                    variant="primary"
                    type="submit"
                    loading={answering}
                    disabled={!suggestion.trim()}
                  >
                    Send changes
                  </Button>
                </div>
              </form>
            ) : null}

            {showEditor ? (
              <div className="fb-code">
                <Suspense fallback={<p className="fb-status">Loading the editor</p>}>
                  <CodeEditor
                    key={current.id}
                    ref={editor}
                    value={content}
                    language={current.language}
                    onChange={edit}
                    onSave={() => void auto.flush()}
                    onHistory={(undo, redo) =>
                      setHistory((h) => (h.undo === undo && h.redo === redo ? h : { undo, redo }))
                    }
                  />
                </Suspense>
              </div>
            ) : kind === 'html' ? (
              <div className="fb-prev fb-prev--page">
                <iframe
                  title={current.title}
                  sandbox=""
                  srcDoc={content}
                  className="fb-prev__frame"
                />
              </div>
            ) : (
              // A press on a tick box inside the rendered text is handled here (the boxes are keyboard-operable themselves).
              <div ref={preview} className="fb-prev" data-keep-scroll onClick={onPreviewClick}>
                <Markdown text={content} className="message-content raw-text-content" />
              </div>
            )}
            {run ? <RunOutput run={run} onClose={() => setRun(null)} /> : null}
          </>
        ) : selected && !detail.isError ? (
          <p className="fb-status" role="status">
            Opening the file
          </p>
        ) : !selected ? (
          <p className="fb-nofile">Pick a file to open it.</p>
        ) : null}
      </div>

      {current && scope.chatId ? (
        <VersionsDialog
          open={showVersions}
          onClose={() => setShowVersions(false)}
          artifactId={current.id}
          fileName={current.title}
          scope={scope}
          onRestored={() => {
            setDraft(null);
            void queryClient.invalidateQueries({ queryKey: ['artifact', current.id, key] });
            void queryClient.invalidateQueries({ queryKey: ['artifact-version', current.id, key] });
          }}
        />
      ) : null}

      <Menu
        label={rowMenu ? `More for ${rowMenu.node.name}` : 'More'}
        point={rowMenu ? { x: rowMenu.x, y: rowMenu.y } : null}
        items={rowItems}
        onClose={() => setRowMenu(null)}
      />
      <FilePlacePopup
        open={place !== null}
        anchorRef={placeAnchor}
        title={place ? PLACE_TEXT[place.kind].title : ''}
        nameLabel={place ? PLACE_TEXT[place.kind].nameLabel : ''}
        confirmLabel={place ? PLACE_TEXT[place.kind].confirm : ''}
        initialName={place?.name ?? ''}
        initialFolder={place?.folder ?? ''}
        folders={folders}
        onSubmit={submitPlace}
        onCancel={() => setPlace(null)}
      />
      <ConfirmDialog
        open={deletingFolder !== null}
        title="Delete this folder?"
        message={`"${deletingFolder ?? ''}" will be deleted. Only an empty folder can be deleted.`}
        confirmLabel="Delete folder"
        danger
        onCancel={() => setDeletingFolder(null)}
        onConfirm={() => {
          const path = deletingFolder;
          setDeletingFolder(null);
          if (path) removeFolder.mutate(path);
        }}
      />
      <ConfirmDialog
        open={deleting !== null}
        title="Delete this file?"
        message={`"${deleting?.title ?? ''}" and its version history will be deleted. This cannot be undone.`}
        confirmLabel="Delete file"
        danger
        onCancel={() => setDeleting(null)}
        onConfirm={() => {
          const target = deleting;
          setDeleting(null);
          if (target) remove.mutate(target.id);
        }}
      />
    </div>
  );
}
