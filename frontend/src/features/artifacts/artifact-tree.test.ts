import { describe, expect, it } from 'vitest';
import type { Artifact } from '../../api/filesystem';
import {
  artifactPath,
  buildTree,
  countFiles,
  folderPaths,
  isRunnable,
  languageForName,
  parentFolder,
  type TreeFolder,
  type TreeNode,
} from './artifact-tree';

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
    const tree = buildTree([
      { filename: 'workspace', title: 'workspace', type: 'file' } as Artifact,
    ]);
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

describe('buildTree placeholder option', () => {
  const dir = (name: string) =>
    ({ id: '', type: 'directory', filename: name, title: name }) as never;
  const file = (path: string) =>
    ({ id: path, type: 'file', filename: path, title: path, language: 'text' }) as never;

  it('hides a lone root `workspace` directory entry when asked', () => {
    expect(buildTree([dir('workspace')], { hidePlaceholder: true })).toEqual([]);
  });

  it('keeps it when a file is under it, and keeps other empty folders', () => {
    const withFile = buildTree([dir('workspace'), file('workspace/a.txt')], {
      hidePlaceholder: true,
    });
    expect(withFile.map((n) => n.name)).toEqual(['workspace']);
    const other = buildTree([dir('workspace'), dir('notes')], { hidePlaceholder: true });
    expect(other.map((n) => n.name)).toEqual(['notes']);
  });

  it('without the option nothing is dropped', () => {
    expect(buildTree([dir('workspace')]).map((n) => n.name)).toEqual(['workspace']);
  });
});

describe('counts, runnable files and languages', () => {
  it('a folder counts its files, including those in folders inside it', () => {
    const tree = buildTree([
      dir('src'),
      file('1', 'a.py', { folder: 'src' }),
      file('2', 'b.py', { folder: 'src/lib' }),
      dir('src/empty'),
    ]);
    expect(countFiles(tree[0] as TreeFolder)).toBe(2);
  });

  it('knows which files the runner accepts', () => {
    expect(isRunnable('src/app.py')).toBe(true);
    expect(isRunnable('Query.SQL')).toBe(true);
    expect(isRunnable('notes.md')).toBe(false);
    expect(isRunnable('Makefile')).toBe(false);
  });

  it("takes a new file's language from its name, markdown when it has no ending", () => {
    expect(languageForName('run.py')).toBe('python');
    expect(languageForName('page.HTML')).toBe('html');
    expect(languageForName('Untitled')).toBe('markdown');
    expect(languageForName('data.csv')).toBe('csv');
  });
});
