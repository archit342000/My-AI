import type { Artifact } from '../../api/filesystem';

export interface TreeFolder {
  kind: 'folder';
  path: string;
  name: string;
  children: TreeNode[];
}

export interface TreeFile {
  kind: 'file';
  path: string;
  name: string;
  artifact: Artifact;
}

export type TreeNode = TreeFolder | TreeFile;

/** True for directory rows (and rows without an id, which the list has always shown as folders). */
export function isDirectoryEntry(a: Artifact): boolean {
  return a.type === 'directory' || !a.id;
}

/**
 * Full slash-separated path of an entry. Disk entries carry the relative path in `filename` and the
 * basename in `title`; virtual entries may carry the folder in `folder` or inside `title`.
 */
export function artifactPath(a: Artifact): string {
  if (isDirectoryEntry(a)) return a.filename || a.title;
  if (a.title.includes('/')) return a.title;
  if (a.folder) return `${a.folder}/${a.title}`;
  if (a.filename.includes('/')) return a.filename;
  return a.title;
}

/** The directory entry the server adds to every file list. */
const PLACEHOLDER_FOLDER = 'workspace';

export interface BuildTreeOptions {
  /**
   * Hides the server's placeholder: the root directory entry named `workspace` (every file list holds one)
   * when nothing is under it, so an empty list shows the panel's empty state. Any other folder is kept.
   */
  hidePlaceholder?: boolean;
}

/** Builds a folder tree from the flat list. Folders come first at every level, then files, each sorted by name. */
export function buildTree(items: Artifact[], options: BuildTreeOptions = {}): TreeNode[] {
  const root: TreeFolder = { kind: 'folder', path: '', name: '', children: [] };
  const folders = new Map<string, TreeFolder>([['', root]]);

  function folder(path: string): TreeFolder {
    const existing = folders.get(path);
    if (existing) return existing;
    const segments = path.split('/');
    const parent = folder(segments.slice(0, -1).join('/'));
    const node: TreeFolder = {
      kind: 'folder',
      path,
      name: segments[segments.length - 1] ?? path,
      children: [],
    };
    parent.children.push(node);
    folders.set(path, node);
    return node;
  }

  for (const item of items) {
    const path = artifactPath(item).replace(/^\/+|\/+$/g, '');
    if (isDirectoryEntry(item)) {
      if (path) folder(path);
      continue;
    }
    const segments = path.split('/');
    const name = segments[segments.length - 1] ?? path;
    folder(segments.slice(0, -1).join('/')).children.push({
      kind: 'file',
      path,
      name,
      artifact: item,
    });
  }

  sortNodes(root.children);
  if (options.hidePlaceholder) {
    return root.children.filter(
      (n) => !(n.kind === 'folder' && n.path === PLACEHOLDER_FOLDER && n.children.length === 0),
    );
  }
  return root.children;
}

function sortNodes(nodes: TreeNode[]): void {
  nodes.sort((a, b) => {
    if (a.kind !== b.kind) return a.kind === 'folder' ? -1 : 1;
    return a.name.localeCompare(b.name, undefined, { sensitivity: 'base', numeric: true });
  });
  for (const node of nodes) if (node.kind === 'folder') sortNodes(node.children);
}

/** Every folder path in a tree, parents before their children (for the move destination list). */
export function folderPaths(nodes: TreeNode[]): string[] {
  const out: string[] = [];
  for (const node of nodes) {
    if (node.kind !== 'folder') continue;
    out.push(node.path);
    out.push(...folderPaths(node.children));
  }
  return out;
}

/** The folder a path is in ('' for the top level). */
export function parentFolder(path: string): string {
  const at = path.lastIndexOf('/');
  return at === -1 ? '' : path.slice(0, at);
}

/** How many files a folder holds, counting the folders inside it. */
export function countFiles(folder: TreeFolder): number {
  let n = 0;
  for (const child of folder.children) n += child.kind === 'file' ? 1 : countFiles(child);
  return n;
}

/** File endings the code runner accepts (`CODE_EXTENSION_MAP` in backend/config.py). */
const RUNNABLE = new Set([
  'py',
  'c',
  'cpp',
  'cc',
  'cxx',
  'java',
  'js',
  'mjs',
  'ts',
  'go',
  'rs',
  'sh',
  'bash',
  'php',
  'sql',
]);

/** True when the file's ending is one the code runner can run. */
export function isRunnable(path: string): boolean {
  const dot = path.lastIndexOf('.');
  return dot !== -1 && RUNNABLE.has(path.slice(dot + 1).toLowerCase());
}

/** The language a new file gets from its name (what the editor and preview go by). */
export function languageForName(name: string): string {
  const dot = name.lastIndexOf('.');
  const ext = dot === -1 ? '' : name.slice(dot + 1).toLowerCase();
  const known: Record<string, string> = {
    md: 'markdown',
    markdown: 'markdown',
    txt: 'text',
    html: 'html',
    htm: 'html',
    css: 'css',
    js: 'javascript',
    mjs: 'javascript',
    jsx: 'jsx',
    ts: 'typescript',
    tsx: 'tsx',
    json: 'json',
    py: 'python',
    c: 'c',
    cpp: 'cpp',
    cc: 'cpp',
    cxx: 'cpp',
    java: 'java',
    go: 'go',
    rs: 'rust',
    sh: 'bash',
    bash: 'bash',
    php: 'php',
    sql: 'sql',
    xml: 'xml',
    yml: 'yaml',
    yaml: 'yaml',
  };
  return known[ext] ?? (ext || 'markdown');
}
