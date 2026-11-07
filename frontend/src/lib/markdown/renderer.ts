/**
 * Markdown pipeline ported from legacy `markdown-renderer.js` and `utils.js#formatMarkdown`.
 * Same renderer overrides, extensions (sub/sup/strikethrough, footnotes, KaTeX) and sanitizer
 * profile. Mermaid and copy/lightbox behaviour are handled by the `<Markdown>` component.
 */
import { Marked, Renderer, type RendererObject, type Tokens } from 'marked';
import markedFootnote from 'marked-footnote';
import markedKatex from 'marked-katex-extension';
import DOMPurify from 'dompurify';
import hljs from 'highlight.js/lib/common';
import { normalizeNewlines, parseContent, preprocessLatex } from './content';

export function escapeHtml(value: string): string {
  return value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

const COPY_ICON =
  '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>';

const ZOOM_ICONS = {
  in: '<line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line>',
  out: '<line x1="5" y1="12" x2="19" y2="12"></line>',
  reset: '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"></path><polyline points="3 3 3 8 8 8"></polyline>',
  popout: '<path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/>',
};

const CALLOUT_ICONS: Record<string, string> = {
  note: '<svg viewBox="0 0 16 16" width="16" height="16" fill="currentColor"><path d="M0 8a8 8 0 1 1 16 0A8 8 0 0 1 0 8Zm8-6.5a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13ZM6.5 7.75A.75.75 0 0 1 7.25 7h1a.75.75 0 0 1 .75.75v2.75h.25a.75.75 0 0 1 0 1.5h-2a.75.75 0 0 1 0-1.5h.25v-2h-.25a.75.75 0 0 1-.75-.75ZM8 6a1 1 0 1 1 0-2 1 1 0 0 1 0 2Z"></path></svg>',
  warning: '<svg viewBox="0 0 16 16" width="16" height="16" fill="currentColor"><path d="M6.457 1.047c.659-1.234 2.427-1.234 3.086 0l6.082 11.396A1.75 1.75 0 0 1 14.082 15H1.918a1.75 1.75 0 0 1-1.543-2.557Zm1.763 1.27a.25.25 0 0 0-.44 0L1.698 13.713a.25.25 0 0 0 .22.387h12.164a.25.25 0 0 0 .22-.387Zm0 2.433a.75.75 0 0 1 1.5 0v3.5a.75.75 0 0 1 0 1.5h-1.5a.75.75 0 0 1 0-1.5v-3.5a.75.75 0 0 1 .75-.75Zm0 8a1 1 0 1 1 0-2 1 1 0 0 1 0 2Z"></path></svg>',
  important: '<svg viewBox="0 0 16 16" width="16" height="16" fill="currentColor"><path d="M0 1.75C0 .784.784 0 1.75 0h12.5C15.216 0 16 .784 16 1.75v9.5A1.75 1.75 0 0 1 14.25 13H8.06l-2.573 2.573A1.458 1.458 0 0 1 3 14.543V13H1.75A1.75 1.75 0 0 1 0 11.25Zm1.75-.25a.25.25 0 0 0-.25.25v9.5c0 .138.112.25.25.25h2a.75.75 0 0 1 .75.75v2.19l2.72-2.72a.75.75 0 0 1 .53-.22h6.5a.25.25 0 0 0 .25-.25v-9.5a.25.25 0 0 0-.25-.25Zm7 2.25v2.5a.75.75 0 0 1-1.5 0v-2.5a.75.75 0 0 1 1.5 0ZM9 9a1 1 0 1 1-2 0 1 1 0 0 1 2 0Z"></path></svg>',
  caution: '<svg viewBox="0 0 16 16" width="16" height="16" fill="currentColor"><path d="M4.47.22A.749.749 0 0 1 5 0h6c.199 0 .389.079.53.22l4.25 4.25c.141.14.22.331.22.53v6a.749.749 0 0 1-.22.53l-4.25 4.25A.749.749 0 0 1 11 16H5a.749.749 0 0 1-.53-.22L.22 11.53A.749.749 0 0 1 0 11V5c0-.199.079-.389.22-.53Zm.84 1.28L1.5 5.31v5.38l3.81 3.81h5.38l3.81-3.81V5.31L10.69 1.5ZM8 4a.75.75 0 0 1 .75.75v3.5a.75.75 0 0 1-1.5 0v-3.5A.75.75 0 0 1 8 4Zm0 8a1 1 0 1 1 0-2 1 1 0 0 1 0 2Z"></path></svg>',
  tip: '<svg viewBox="0 0 16 16" width="16" height="16" fill="currentColor"><path d="M8 1.5c-2.363 0-4 1.69-4 3.75 0 .984.424 1.625.984 2.304l.214.253c.223.264.47.556.673.848.284.411.537.896.621 1.49a.75.75 0 0 1-1.484.211c-.04-.282-.163-.547-.37-.843a5.314 5.314 0 0 1-.675-.848 5.463 5.463 0 0 1-.215-.254C3.176 7.674 2.5 6.641 2.5 5.25 2.5 2.31 4.863 0 8 0s5.5 2.31 5.5 5.25c0 1.391-.676 2.424-1.248 3.161l-.215.254a5.314 5.314 0 0 1-.675.848c-.207.296-.33.561-.37.843a.75.75 0 0 1-1.484-.21c.084-.594.337-1.079.621-1.49.203-.292.45-.584.673-.848.075-.088.147-.173.214-.253.56-.679.984-1.32.984-2.304 0-2.06-1.637-3.75-4-3.75ZM5.75 12h4.5a.75.75 0 0 1 0 1.5h-4.5a.75.75 0 0 1 0-1.5ZM6 15.25a.75.75 0 0 1 .75-.75h2.5a.75.75 0 0 1 0 1.5h-2.5a.75.75 0 0 1-.75-.75Z"></path></svg>',
};

const baseRenderer = new Renderer();

/* marked only copies own enumerable properties of a renderer object, so overrides are plain functions. */
const legacyRenderer: RendererObject = {
  code({ text, lang }: Tokens.Code): string {
    const language = lang && hljs.getLanguage(lang) ? lang : 'plaintext';
    if (lang === 'mermaid') {
      return `<div class="mermaid-wrapper-container">
  <div class="mermaid-controls">
    <button class="mermaid-ctrl-btn zoom-in-btn" title="Zoom In"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${ZOOM_ICONS.in}</svg></button>
    <button class="mermaid-ctrl-btn zoom-out-btn" title="Zoom Out"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${ZOOM_ICONS.out}</svg></button>
    <button class="mermaid-ctrl-btn zoom-reset-btn" title="Reset Zoom"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${ZOOM_ICONS.reset}</svg></button>
    <button class="mermaid-ctrl-btn zoom-popout-btn" title="Pop Out / Fullscreen"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${ZOOM_ICONS.popout}</svg></button>
  </div>
  <div class="mermaid-pan-viewport"><pre class="mermaid">${escapeHtml(text)}</pre></div>
</div>`;
    }
    const highlighted = hljs.highlight(text, { language }).value;
    return `<div class="code-block-wrapper">
  <div class="code-block-header">
    <span class="code-block-lang">${language}</span>
    <button class="action-btn copy-code-btn" data-code="${encodeURIComponent(text)}" title="Copy code">${COPY_ICON}<span>Copy</span></button>
  </div>
  <pre><code class="hljs language-${language}">${highlighted}</code></pre>
</div>`;
  },
  image({ href, title, text }: Tokens.Image): string {
    let out = `<img src="${href}" alt="${text || ''}" class="markdown-image lightbox-img" loading="lazy" ${title ? `title="${title}"` : ''} />`;
    if (title || text) {
      out = `<figure class="markdown-figure">${out}<figcaption class="markdown-caption">${title || text}</figcaption></figure>`;
    }
    return out;
  },
  blockquote(this: Renderer, token: Tokens.Blockquote): string {
    const inner = this.parser.parse(token.tokens);
    const match = inner.match(/^<p>\[!(NOTE|WARNING|IMPORTANT|CAUTION|TIP)\](?:<br>|\n)?([\s\S]*)$/i);
    if (!match) return `<blockquote>\n${inner}</blockquote>\n`;
    const type = (match[1] ?? 'note').toLowerCase();
    let content = match[2] ?? '';
    if (content.endsWith('</p>\n')) content = content.slice(0, -5) + '</p>';
    const label = type.charAt(0).toUpperCase() + type.slice(1);
    return `<blockquote class="markdown-alert markdown-alert-${type}">
  <div class="markdown-alert-title">${CALLOUT_ICONS[type] ?? CALLOUT_ICONS.note}<span>${label}</span></div>
  <div class="markdown-alert-content">${content}</div>
</blockquote>\n`;
  },
  listitem(this: Renderer, item: Tokens.ListItem): string {
    if (item.task) {
      const content = this.parser.parseInline(item.tokens);
      return `<li class="task-list-item" style="list-style-type: none; margin-left: -1.5rem; display: flex; align-items: flex-start; gap: 0.5rem; margin-bottom: 0.25rem;">
  <input type="checkbox" class="task-list-item-checkbox" ${item.checked ? 'checked' : ''} disabled style="margin-top: 0.25rem;">
  <span>${content}</span>
</li>\n`;
    }
    return `<li>${this.parser.parse(item.tokens)}</li>\n`;
  },
  link({ href, title, text }: Tokens.Link): string {
    if (href && !/^https?:\/\//i.test(href) && !/^[/#]/.test(href) && !/^(mailto|tel):/.test(href)) {
      return `<a href="${href}" class="file-link" data-path="${href}" title="Open file in workspace">${text}</a>`;
    }
    const titleAttr = title ? ` title="${title}"` : '';
    return `<a href="${href}"${titleAttr} target="_blank" rel="noopener noreferrer">${text}</a>`;
  },
  table(this: Renderer, token: Tokens.Table): string {
    return `<div class="table-wrapper">${baseRenderer.table.call(this, token)}</div>`;
  },
};

/** Inline extensions: subscript, superscript, strikethrough. */
const subscript = {
  name: 'subscript',
  level: 'inline' as const,
  start(src: string) {
    return src.match(/~(?=\S)/)?.index;
  },
  tokenizer(this: { lexer: { inlineTokens(s: string): Tokens.Generic[] } }, src: string) {
    const match = /^~((?:\\.|[^~])+)~/.exec(src);
    if (match) return { type: 'subscript', raw: match[0], text: match[1], tokens: this.lexer.inlineTokens(match[1] ?? '') };
    return undefined;
  },
  renderer(this: { parser: { parseInline(t: Tokens.Generic[]): string } }, token: Tokens.Generic) {
    return `<sub>${this.parser.parseInline((token as unknown as { tokens: Tokens.Generic[] }).tokens)}</sub>`;
  },
};

const superscript = {
  name: 'superscript',
  level: 'inline' as const,
  start(src: string) {
    return src.match(/\^(?=\S)/)?.index;
  },
  tokenizer(this: { lexer: { inlineTokens(s: string): Tokens.Generic[] } }, src: string) {
    const match = /^\^((?:\\.|[^^])+)\^/.exec(src);
    if (match) return { type: 'superscript', raw: match[0], text: match[1], tokens: this.lexer.inlineTokens(match[1] ?? '') };
    return undefined;
  },
  renderer(this: { parser: { parseInline(t: Tokens.Generic[]): string } }, token: Tokens.Generic) {
    return `<sup>${this.parser.parseInline((token as unknown as { tokens: Tokens.Generic[] }).tokens)}</sup>`;
  },
};

const strikethrough = {
  name: 'strikethrough',
  level: 'inline' as const,
  start(src: string) {
    return src.match(/~~(?=\S)/)?.index;
  },
  tokenizer(this: { lexer: { inlineTokens(s: string): Tokens.Generic[] } }, src: string) {
    const match = /^~~((?:\\.|[^~])+)~~/.exec(src);
    if (match) return { type: 'strikethrough', raw: match[0], text: match[1], tokens: this.lexer.inlineTokens(match[1] ?? '') };
    return undefined;
  },
  renderer(this: { parser: { parseInline(t: Tokens.Generic[]): string } }, token: Tokens.Generic) {
    return `<del>${this.parser.parseInline((token as unknown as { tokens: Tokens.Generic[] }).tokens)}</del>`;
  },
};

const marked = new Marked({ renderer: legacyRenderer, extensions: [subscript, superscript, strikethrough] });
marked.use(markedFootnote());
marked.use(markedKatex({ throwOnError: false, nonStandard: true }));

/** Full legacy `formatMarkdown` pipeline: think-tag extraction, newline normalisation, marked, DOMPurify. */
export function renderMarkdown(text: string | null | undefined): string {
  if (!text) return '';
  const { cleaned } = parseContent(text);
  let normalized = preprocessLatex(normalizeNewlines(cleaned));
  const trimmed = normalized.trim();
  if (trimmed.startsWith('<') && (trimmed.includes('</') || trimmed.endsWith('/>')) && !trimmed.startsWith('```')) {
    normalized = '```xml\n' + normalized + '\n```';
  }
  const html = marked.parse(normalized, { breaks: true, async: false }) as string;
  return DOMPurify.sanitize(html, {
    USE_PROFILES: { html: true, mathMl: true, svg: true },
    ADD_ATTR: ['target', 'aria-hidden', 'xmlns', 'encoding'],
  });
}
