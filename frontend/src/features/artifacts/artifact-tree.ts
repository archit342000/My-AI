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

/** Builds a folder tree from the flat list. Folders come first at every level, then files, each sorted by name. */
export function buildTree(items: Artifact[]): TreeNode[] {
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
    folder(segments.slice(0, -1).join('/')).children.push({ kind: 'file', path, name, artifact: item });
  }

  sortNodes(root.children);
  return root.children;
}

function sortNodes(nodes: TreeNode[]): void {
  nodes.sort((a, b) => {
    if (a.kind !== b.kind) return a.kind === 'folder' ? -1 : 1;
    return a.name.localeCompare(b.name, undefined, { sensitivity: 'base', numeric: true });
  });
  for (const node of nodes) if (node.kind === 'folder') sortNodes(node.children);
}
