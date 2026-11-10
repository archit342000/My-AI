import { describe, expect, it } from 'vitest';
import type { Artifact } from '../../api/filesystem';
import { searchFiles } from './file-search';

const f = (id: string, title: string, folder?: string): Artifact => ({
  id,
  title,
  filename: title,
  type: 'file',
  folder,
});
const items = [
  f('a', 'notes.md'),
  f('b', 'app.py', 'src'),
  { id: '', title: 'src', filename: 'src/', type: 'directory' },
];

describe('searchFiles', () => {
  it('finds nothing for an empty search', () => {
    expect(searchFiles(items, new Map(), '  ')).toEqual([]);
  });

  it('matches names and folders, whatever the case, and never lists a folder', () => {
    expect(searchFiles(items, new Map(), 'SRC').map((h) => h.path)).toEqual(['src/app.py']);
    expect(searchFiles(items, new Map(), 'notes').map((h) => h.path)).toEqual(['notes.md']);
  });

  it('searches the text of loaded files and gives the first matching line', () => {
    const contents = new Map([['a', 'one\n  two apples  \nthree apples']]);
    expect(searchFiles(items, contents, 'apples')).toEqual([
      { artifact: items[0], path: 'notes.md', line: { number: 2, text: 'two apples' } },
    ]);
  });

  it('lists name matches before text matches, and a file only once', () => {
    const contents = new Map([
      ['a', 'app is mentioned here'],
      ['b', 'app = 1'],
    ]);
    const hits = searchFiles(items, contents, 'app');
    expect(hits.map((h) => h.path)).toEqual(['src/app.py', 'notes.md']);
    expect(hits[0]?.line).toEqual({ number: 1, text: 'app = 1' });
  });

  it('cuts a very long line around the words searched for', () => {
    const long = `${'x'.repeat(300)} needle ${'y'.repeat(300)}`;
    const text = searchFiles(items, new Map([['a', long]]), 'needle')[0]?.line?.text ?? '';
    expect(text).toContain('needle');
    expect(text.length).toBeLessThan(170);
    expect(text.startsWith('…')).toBe(true);
  });
});
