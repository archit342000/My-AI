/**
 * Content pre-processing ported from legacy `utils.js` (`parseContent`, `preprocessLatex`).
 */

export interface ParsedContent {
  thoughts: string;
  cleaned: string;
}

/**
 * Extracts `<think>...</think>` blocks into `thoughts`. An unclosed tag hides everything after it
 * (matches legacy behaviour and logs a warning).
 */
export function parseContent(text: string): ParsedContent {
  if (!text) return { thoughts: '', cleaned: '' };
  let cleaned = text;
  let thoughts = '';
  let start = cleaned.indexOf('<think>');
  while (start !== -1) {
    const end = cleaned.indexOf('</think>', start + 7);
    if (end !== -1) {
      thoughts += (thoughts ? '\n' : '') + cleaned.substring(start + 7, end);
      cleaned = cleaned.substring(0, start) + cleaned.substring(end + '</think>'.length).trim();
    } else {
      console.warn('[parseContent] Unclosed <think> tag; content after it is hidden.');
      thoughts += (thoughts ? '\n' : '') + cleaned.substring(start + 7);
      cleaned = cleaned.substring(0, start);
      break;
    }
    start = cleaned.indexOf('<think>');
  }
  return { thoughts: thoughts.trim(), cleaned: cleaned.trim() };
}

/** Pads multi-line `$$ ... $$` blocks so the KaTeX block rule can match them. */
export function preprocessLatex(text: string): string {
  if (!text) return text;
  return text.replace(/\$\$(.+?)\$\$/gs, (match, content: string) => {
    if (content.includes('\n')) return `\n\n$$\n${content.trim()}\n$$\n\n`;
    return match;
  });
}

/**
 * Turns literal `\n` sequences (not followed by a letter) into newlines, as legacy did, but only
 * for a JSON-escaped blob: a message with real line breaks is left alone, and so is anything inside
 * a backtick code span (a `"Semantic Graph:\n"` string in code must stay as written).
 */
export function normalizeNewlines(text: string): string {
  if (text.includes('\n')) return text;
  // Odd indexes are the captured code spans; even indexes are prose.
  return text
    .split(/(`+[^`]*?`+)/)
    .map((part, index) => (index % 2 === 1 ? part : part.replace(/\\n(?![a-zA-Z])/g, '\n')))
    .join('');
}
