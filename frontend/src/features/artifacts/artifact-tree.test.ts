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
