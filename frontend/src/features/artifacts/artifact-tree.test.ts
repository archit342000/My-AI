import { describe, expect, it } from 'vitest';
import type { Artifact } from '../../api/filesystem';
import { artifactPath, buildTree, folderPaths, parentFolder, type TreeNode } from './artifact-tree';

const file = (id: string, title: string, extra: Partial<Artifact> = {}): Artifact => ({
  id,
  filename: title,
  title,
  type: 'file',
  ...extra,
});

const dir = (path: string): Artifact => ({
  id: '',
  filename: path,
  title: path.split('/').pop() ?? path,
  type: 'directory',
});

function shape(nodes: TreeNode[]): unknown {
  return nodes.map((n) => (n.kind === 'folder' ? { [n.name + '/']: shape(n.children) } : n.name));
}

describe('buildTree', () => {
  it('puts directories before files at each level and sorts by name', () => {
    const tree = buildTree([
      file('1', 'zeta.md'),
      file('2', 'alpha.md'),
      dir('src'),
      file('3', 'src/utils.ts'),
      dir('docs'),
    ]);
    expect(shape(tree)).toEqual([{ 'docs/': [] }, { 'src/': ['utils.ts'] }, 'alpha.md', 'zeta.md']);
  });

  it('creates missing parent folders for nested files', () => {
    const tree = buildTree([file('1', 'a/b/c.md')]);
    expect(shape(tree)).toEqual([{ 'a/': [{ 'b/': ['c.md'] }] }]);
  });

  it('uses the folder field for virtual files with a bare title', () => {
    expect(artifactPath(file('1', 'note.md', { folder: 'notes' }))).toBe('notes/note.md');
  });

  it('keeps entries without an id as folders', () => {
    const tree = buildTree([{ filename: 'workspace', title: 'workspace', type: 'file' } as Artifact]);
    expect(shape(tree)).toEqual([{ 'workspace/': [] }]);
  });
});

describe('folderPaths and parentFolder', () => {
  it('lists every folder, parents first, and finds the folder of a path', () => {
    const items = [
      { id: '', type: 'directory', filename: 'notes/2026', title: 'notes/2026' },
      { id: 'f', type: 'file', filename: 'a.md', title: 'zeta/a.md', language: 'markdown' },
    ] as never;
    expect(folderPaths(buildTree(items))).toEqual(['notes', 'notes/2026', 'zeta']);
    expect(parentFolder('notes/2026/a.md')).toBe('notes/2026');
    expect(parentFolder('a.md')).toBe('');
  });
});
