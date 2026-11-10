import { describe, expect, it } from 'vitest';
import { splitBlocks } from './blocks';

const join = (blocks: string[]) => blocks.join('\n');

describe('splitBlocks', () => {
  it('splits paragraphs at blank lines and joins back to the input', () => {
    const text = 'one\n\ntwo\n\nthree';
    const blocks = splitBlocks(text);
    expect(blocks).toHaveLength(3);
    expect(join(blocks)).toBe(text);
  });

  it('does not split inside a fenced code block', () => {
    const text = 'before\n\n```js\nconst a = 1;\n\nconst b = 2;\n```\n\nafter';
    const blocks = splitBlocks(text);
    expect(blocks.filter((b) => b.includes('const a'))).toHaveLength(1);
    expect(blocks.find((b) => b.includes('const a'))).toContain('const b');
    expect(join(blocks)).toBe(text);
  });

  it('does not split inside a $$ math block', () => {
    const text = 'x\n\n$$\na = b\n\nc = d\n$$\n\ny';
    const blocks = splitBlocks(text);
    expect(blocks.find((b) => b.includes('a = b'))).toContain('c = d');
    expect(join(blocks)).toBe(text);
  });

  it('keeps an unclosed fence together as one growing block', () => {
    const text = 'intro\n\n```\nline\n\nmore';
    const blocks = splitBlocks(text);
    expect(blocks.at(-1)).toContain('more');
    expect(blocks.at(-1)).toContain('```');
    expect(join(blocks)).toBe(text);
  });

  it('handles empty text and a trailing blank line without an empty block', () => {
    expect(splitBlocks('')).toEqual([]);
    const blocks = splitBlocks('a\n\n');
    expect(join(blocks)).toBe('a\n\n');
    expect(blocks.every((b) => b.trim() !== '')).toBe(true);
    const leading = splitBlocks('\n\nfirst\n\nsecond\n\n\n');
    expect(leading.every((b) => b.trim() !== '')).toBe(true);
    expect(join(leading)).toBe('\n\nfirst\n\nsecond\n\n\n');
  });

  it('returns no block for whitespace-only text', () => {
    expect(splitBlocks('\n')).toEqual([]);
    expect(splitBlocks('  \n \n')).toEqual([]);
  });

  it('keeps a $$ block that opens on a line with text together across a blank line', () => {
    const text = '$$ x =\n\ny $$\n\nafter';
    const blocks = splitBlocks(text);
    expect(blocks).toHaveLength(2);
    expect(blocks[0]).toContain('y $$');
    expect(join(blocks)).toBe(text);
    expect(splitBlocks('$$ a $$\n\nnext')).toHaveLength(2);
  });

  it('does not let a stray $$ at the start of a line swallow the rest of the reply', () => {
    const text = '$$5 is the price\n\nSecond para\n\nThird';
    expect(splitBlocks(text)).toHaveLength(3);
    // a $$ that does close later still keeps its block together
    expect(splitBlocks('$$ x =\n\ny $$\n\nz')).toHaveLength(2);
  });

  it('does not treat inline code at the start of a line as a fence', () => {
    const text = '```x``` is code\n\nnext paragraph';
    expect(splitBlocks(text)).toHaveLength(2);
  });

  it('handles tilde fences, indented fences and CRLF line endings', () => {
    const tilde = '~~~\na\n\nb\n~~~\n\nafter';
    expect(splitBlocks(tilde).find((b) => b.includes('a\n'))).toContain('b');
    const indented = '  ```\n  a\n\n  b\n  ```\n\nafter';
    expect(splitBlocks(indented).find((b) => b.includes('  a'))).toContain('  b');
    const crlf = 'one\r\n\r\ntwo\r\n\r\n```\r\nx\r\n\r\ny\r\n```';
    const blocks = splitBlocks(crlf);
    expect(blocks).toHaveLength(3);
    expect(join(blocks)).toBe(crlf);
  });

  it('splits a loose list and a table at their blank lines (they render per block until saved)', () => {
    const list = '1. a\n\n2. b';
    expect(splitBlocks(list)).toHaveLength(2);
    const table = '| a | b |\n|---|---|\n| 1 | 2 |\n\nafter';
    expect(splitBlocks(table)[0]).toContain('| 1 | 2 |');
  });

  it('a longer fence is not closed by a shorter one', () => {
    const text = '````\n```\n\ninner\n````\n\nafter';
    const blocks = splitBlocks(text);
    expect(blocks.find((b) => b.includes('inner'))).toContain('````');
    expect(join(blocks)).toBe(text);
  });
});
