import { describe, expect, it } from 'vitest';
import type { Artifact } from '../../api/filesystem';
import { artifactPath, buildTree, type TreeNode } from './artifact-tree';

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

describe('buildTree placeholder option', () => {
  const dir = (name: string) => ({ id: '', type: 'directory', filename: name, title: name }) as never;
  const file = (path: string) =>
    ({ id: path, type: 'file', filename: path, title: path, language: 'text' }) as never;

  it('hides a lone root `workspace` directory entry when asked', () => {
    expect(buildTree([dir('workspace')], { hidePlaceholder: true })).toEqual([]);
  });

  it('keeps it when a file is under it, and keeps other empty folders', () => {
    const withFile = buildTree([dir('workspace'), file('workspace/a.txt')], { hidePlaceholder: true });
    expect(withFile.map((n) => n.name)).toEqual(['workspace']);
    const other = buildTree([dir('workspace'), dir('notes')], { hidePlaceholder: true });
    expect(other.map((n) => n.name)).toEqual(['notes']);
  });

  it('without the option nothing is dropped', () => {
    expect(buildTree([dir('workspace')]).map((n) => n.name)).toEqual(['workspace']);
  });
});
