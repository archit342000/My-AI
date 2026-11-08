import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative, resolve } from 'node:path';

/** Absolute path of the frontend `src/` directory (vitest and npm scripts run from `frontend/`). */
export const SRC_DIR = resolve(process.cwd(), 'src');

/** Recursively lists files under `dir` whose name matches `pattern`, as paths relative to `src/`. */
export function listFiles(dir: string, pattern: RegExp): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) {
      out.push(...listFiles(full, pattern));
    } else if (pattern.test(entry)) {
      out.push(relative(SRC_DIR, full).split('\\').join('/'));
    }
  }
  return out.sort();
}

export function readSrc(relPath: string): string {
  return readFileSync(join(SRC_DIR, relPath), 'utf8');
}

/**
 * Returns every static class name written in a `className` attribute of the given source text.
 * Handles string literals, template literals (with `${…}` expressions removed) and ternaries.
 */
export function classNamesInSource(source: string): Set<string> {
  const found = new Set<string>();
  const attr = /className\s*=\s*/g;
  let match: RegExpExecArray | null;
  while ((match = attr.exec(source)) !== null) {
    const start = match.index + match[0].length;
    const first = source[start];
    let body: string;
    if (first === '"' || first === "'") {
      const end = source.indexOf(first, start + 1);
      body = source.slice(start, end + 1);
    } else if (first === '{') {
      body = source.slice(start, matchingBrace(source, start) + 1);
    } else {
      continue;
    }
    for (const literal of body.matchAll(/(["'`])((?:\\.|(?!\1).)*?)\1/gs)) {
      const text = (literal[2] ?? '').replace(/\$\{[^}]*\}/g, ' ');
      for (const token of text.split(/\s+/)) {
        if (/^-?[a-zA-Z_][\w-]*$/.test(token)) found.add(token);
      }
    }
  }
  return found;
}

function matchingBrace(source: string, open: number): number {
  let depth = 0;
  for (let i = open; i < source.length; i++) {
    const ch = source[i];
    if (ch === '{') depth++;
    else if (ch === '}') {
      depth--;
      if (depth === 0) return i;
    }
  }
  throw new Error(`Unbalanced braces after offset ${open}`);
}

/** Returns every class selector mentioned in a stylesheet (comments stripped). */
export function classSelectorsInCss(css: string): Set<string> {
  const stripped = css.replace(/\/\*[\s\S]*?\*\//g, '');
  const found = new Set<string>();
  for (const m of stripped.matchAll(/(?<![\d.\\])\.(-?[_a-zA-Z][\w-]*)/g)) {
    found.add(m[1]!);
  }
  return found;
}
