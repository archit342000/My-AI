import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative, resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

/** Variables set at run time with style.setProperty, never declared in a stylesheet. */
const SET_FROM_SCRIPT = new Set([
  '--artifact-width',
  '--composer-h',
  '--fill',
  '--keyboard-offset',
  '--progress',
  '--right-sidebar-width',
  '--sidebar-expanded-width',
]);

/** Legacy names read by a rule but defined nowhere (they fall back to the property's default). */
const KNOWN_UNDEFINED = [
  '--bg-card',
  '--color-primary-light',
  '--color-sky-500',
  '--shadow-sm',
  '--surface-1',
  '--surface-2',
  '--surface-3',
  '--surface-4',
  '--surface-primary',
  '--surface-tertiary',
  '--text-main',
];

// Guards the rule that colours come only from the shared values (src/styles/tokens.css).

const SRC = resolve(__dirname, '..');
const HEX_COLOUR = /#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b/;

function read(path: string): string {
  return readFileSync(join(SRC, path), 'utf8');
}

function componentFiles(dir: string, found: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) componentFiles(path, found);
    else if (name.endsWith('.tsx') && !name.includes('.test.') && !name.includes('.generated.'))
      found.push(path);
  }
  return found;
}

/** Lines holding a hex colour, ignoring comments. */
function hexLines(text: string): string[] {
  return text
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .split('\n')
    .filter((line) => !line.trim().startsWith('//') && HEX_COLOUR.test(line));
}

describe('design tokens', () => {
  it('tokens.css starts with the stamp the sync script writes (version and commit)', () => {
    const first = read('styles/tokens.css').split('\n')[0];
    expect(first).toMatch(
      /^\/\* Synced from console-at-rest v\d+\.\d+ @ [0-9a-f]{7,}\. Do not edit: run scripts\/sync-design-tokens\.cjs\. \*\/$/,
    );
  });

  it('bridge.css and fonts.css contain no hex colour (--accent-rgb is the one mirrored value, checked below)', () => {
    expect(hexLines(read('styles/bridge.css'))).toEqual([]);
    expect(hexLines(read('styles/fonts.css'))).toEqual([]);
  });

  it('the design system sheets (styles/ds) contain no hex colour', () => {
    for (const name of readdirSync(join(SRC, 'styles/ds'))) {
      expect(hexLines(read(`styles/ds/${name}`)), name).toEqual([]);
    }
  });

  it('no component file contains a hex colour', () => {
    const offenders = componentFiles(SRC)
      .filter((file) => hexLines(readFileSync(file, 'utf8')).length > 0)
      .map((file) => relative(SRC, file));
    expect(offenders, 'Use a shared value from tokens.css instead').toEqual([]);
  });

  it('the hex check itself catches a colour and ignores comments', () => {
    expect(hexLines("const c = '#0B6BCB';")).toHaveLength(1);
    expect(hexLines('a { color: #fff; }')).toHaveLength(1);
    expect(hexLines('/* #0B6BCB in a comment */\n// #fff too\nconst ok = 1;')).toEqual([]);
  });

  it('--accent-rgb in bridge.css repeats --accent from tokens.css, in both themes', () => {
    const tokens = read('styles/tokens.css');
    const bridge = read('styles/bridge.css');
    const triplet = (hex: string) =>
      [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16)).join(', ');
    // Each lookup stays inside its own block ([^}]*), so a missing --accent cannot match a later block.
    const day = /:root \{[^}]*?--accent: (#[0-9A-Fa-f]{6});/.exec(tokens)?.[1];
    const night = /:root\[data-theme="dark"\] \{[^}]*?--accent: (#[0-9A-Fa-f]{6});/.exec(
      tokens,
    )?.[1];
    expect(day, 'day --accent in tokens.css').toBeDefined();
    expect(night, 'night --accent in tokens.css').toBeDefined();
    const bridged = [...bridge.matchAll(/--accent-rgb: ([\d, ]+);/g)].map((m) => m[1]);
    expect(bridged).toEqual([triplet(day ?? ''), triplet(night ?? '')]);
  });

  it('every variable the stylesheets read is defined somewhere (bridge and renames left no gap)', () => {
    const sheets = ['fonts', 'legacy', 'components', 'tokens', 'bridge']
      .map((name) => read(`styles/${name}.css`))
      .join('\n');
    const used = new Set([...sheets.matchAll(/var\(\s*(--[a-zA-Z0-9-]+)/g)].map((m) => m[1]));
    const defined = new Set([...sheets.matchAll(/(--[a-zA-Z0-9-]+)\s*:/g)].map((m) => m[1]));
    const missing = [...used].filter(
      (name) => !defined.has(name) && !SET_FROM_SCRIPT.has(name ?? ''),
    );
    // These were already undefined before the shared values arrived. The list may only shrink.
    expect(missing.sort()).toEqual([...KNOWN_UNDEFINED].sort());
  });
});
