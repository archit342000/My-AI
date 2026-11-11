import { afterEach, describe, expect, it, vi } from 'vitest';
import { fadePadding, fadePatches, measureWords } from './sphere-fade';

afterEach(() => vi.restoreAllMocks());

describe('fadePadding', () => {
  it('grows with the lettering between fixed limits', () => {
    expect(fadePadding(16)).toEqual({ x: 8, y: 4 });
    expect(fadePadding(80)).toEqual({ x: 80 * 0.14, y: 80 * 0.06 });
    expect(fadePadding(400)).toEqual({ x: 14, y: 8 });
  });
});

describe('fadePatches', () => {
  it('places a padded patch per box, relative to the container, and drops empty boxes', () => {
    const patches = fadePatches(
      [
        { left: 120, top: 220, width: 300, height: 20 },
        { left: 120, top: 260, width: 0, height: 20 },
        { left: 120, top: 300, width: 90, height: 44 },
      ],
      { left: 100, top: 200 },
    );
    expect(patches).toEqual([
      { left: 12, top: 16, width: 316, height: 28 },
      { left: 12, top: 96, width: 106, height: 52 },
    ]);
  });
});

describe('measureWords', () => {
  it('measures buttons and status lights, and ignores the fade layer itself', () => {
    const host = document.createElement('div');
    host.innerHTML =
      '<div class="fade-layer"><i>x</i></div><p>Hello</p><span class="led"></span><button>Go</button>';
    document.body.appendChild(host);
    // jsdom has no layout: every box is empty, but each control is still measured once.
    expect(measureWords(host)).toHaveLength(2);
    host.remove();
  });

  it('measures each line of text, but not text inside the fade layer', () => {
    const line = { left: 1, top: 2, width: 30, height: 10 } as DOMRect;
    const selected: string[] = [];
    vi.spyOn(document, 'createRange').mockReturnValue({
      selectNodeContents: (node: Node) => selected.push(node.nodeValue ?? ''),
      getClientRects: () => [line],
    } as unknown as Range);
    const host = document.createElement('div');
    host.innerHTML = '<div class="fade-layer"><i>x</i></div><p>Hello</p><p>there</p>';
    document.body.appendChild(host);
    expect(measureWords(host)).toEqual([line, line]);
    expect(selected).toEqual(['Hello', 'there']);
    host.remove();
  });
});
