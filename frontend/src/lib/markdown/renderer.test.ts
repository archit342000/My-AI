import { describe, expect, it } from 'vitest';
import { renderMarkdown } from './renderer';
import { parseContent, preprocessLatex, normalizeNewlines } from './content';

describe('parseContent', () => {
  it('moves <think> blocks into thoughts', () => {
    expect(parseContent('<think>plan</think>\nAnswer')).toEqual({
      thoughts: 'plan',
      cleaned: 'Answer',
    });
  });
  it('hides everything after an unclosed <think>', () => {
    expect(parseContent('Hi <think>never closed')).toEqual({
      thoughts: 'never closed',
      cleaned: 'Hi',
    });
  });
});

describe('preprocessLatex / normalizeNewlines', () => {
  it('pads multi-line display math', () => {
    expect(preprocessLatex('a $$x\ny$$ b')).toContain('\n\n$$\nx\ny\n$$\n\n');
  });
  it('converts literal \\n sequences', () => {
    expect(normalizeNewlines('a\\n1')).toBe('a\n1');
    expect(normalizeNewlines('a\\nb')).toBe('a\\nb'); // legacy: not before a letter
  });
  it('leaves code with literal \\n untouched (F-05)', () => {
    // Inline code spans are never rewritten, even in a single-line message.
    expect(normalizeNewlines('Use `"Semantic Graph:\\n"` in code')).toBe(
      'Use `"Semantic Graph:\\n"` in code',
    );
    // Multi-line code (real newlines present) is never rewritten.
    const fenced = '```py\nprint("Semantic Graph:\\n")\nf(x\\n)\n```';
    expect(normalizeNewlines(fenced)).toBe(fenced);
  });
  it('does not rewrite a message that already has real line breaks (F-05)', () => {
    const text = 'Line one\nreads "a\\n" literally';
    expect(normalizeNewlines(text)).toBe(text);
  });
});

describe('renderMarkdown', () => {
  it('renders headings and emphasis', () => {
    const html = renderMarkdown('# Title\n\n**bold**');
    expect(html).toContain('<h1');
    expect(html).toContain('<strong>bold</strong>');
  });

  it('wraps code in a highlighted block with a copy button', () => {
    const html = renderMarkdown('```python\nprint(1)\n```');
    expect(html).toContain('code-block-wrapper');
    expect(html).toContain('copy-code-btn');
    expect(html).toContain('language-python');
  });

  it('emits a mermaid container for mermaid fences', () => {
    const html = renderMarkdown('```mermaid\ngraph TD; A-->B\n```');
    expect(html).toContain('mermaid-wrapper-container');
    expect(html).toContain('<pre class="mermaid">');
  });

  it('turns GitHub-style alerts into callouts', () => {
    const html = renderMarkdown('> [!WARNING]\n> Careful here');
    expect(html).toContain('markdown-alert-warning');
    expect(html).toContain('Careful here');
  });

  it('wraps tables for horizontal scrolling', () => {
    const html = renderMarkdown('| a | b |\n|---|---|\n| 1 | 2 |');
    expect(html).toContain('table-wrapper');
  });

  it('supports sub, sup and strikethrough', () => {
    const html = renderMarkdown('H~2~O x^2^ ~~gone~~');
    expect(html).toContain('<sub>2</sub>');
    expect(html).toContain('<sup>2</sup>');
    expect(html).toContain('<del>gone</del>');
  });

  it('renders KaTeX math', () => {
    expect(renderMarkdown('Inline $x^2$ here')).toContain('katex');
  });

  it('sanitises scripts and event handlers', () => {
    const html = renderMarkdown('hi <img src=x onerror="alert(1)"><script>alert(2)</script>');
    expect(html).not.toContain('onerror');
    expect(html).not.toContain('<script');
  });

  it('renders file-like relative links as file-link', () => {
    expect(renderMarkdown('[notes](notes.md)')).toContain('class="file-link"');
  });

  it('returns empty string for empty input', () => {
    expect(renderMarkdown('')).toBe('');
  });

  it('a task list item has one tick box, written without inline styles', () => {
    const html = renderMarkdown('- [x] done\n- [ ] to do');
    expect(html.match(/type="checkbox"/g)).toHaveLength(2);
    expect(html).toContain('class="task-list-item-checkbox" checked');
    expect(html).not.toContain('style=');
  });
});
