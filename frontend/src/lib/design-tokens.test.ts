import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative, resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

// Guards the rule that colours, corners, shadows, layers and speeds come only from the shared values
// (src/styles/tokens.css, a synced copy of the Console at Rest design system).

const SRC = resolve(__dirname, '..');
const DS = 'styles/ds';

/** Variables set at run time with style.setProperty (or as an inline custom property), never declared in a sheet. */
const SET_FROM_SCRIPT = new Set([
  '--artifact-width',
  '--composer-h',
  '--fill',
  '--keyboard-offset',
  '--progress',
  '--sidebar-expanded-width',
  '--sidebar-width',
  '--skel-w',
  '--skel-h',
]);

/**
 * Corner shapes that are not one of the four shared sizes, each with its reason. Small inner pieces
 * (8 and under) are allowed as a class below; anything else needs a line here.
 */
const CORNER_ONE_OFFS: Record<string, string> = {
  'controls.css|12px 0 0 3px': 'left half of a joined field (the control corner, split)',
  'controls.css|0 12px 12px 0': 'right half of a joined field (the control corner, split)',
  'controls.css|14px 14px 14px 4px': 'the switch track: half its height, with the squared corner',
  'chat.css|14px 14px 14px 3px': "the person's message bubble (reference: .msg-user)",
};

const HEX_COLOUR = /#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b/;
const RAW_COLOUR =
  /#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b|\b(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch)\(/;

function read(path: string): string {
  return readFileSync(join(SRC, path), 'utf8');
}
const withoutComments = (text: string) => text.replace(/\/\*[\s\S]*?\*\//g, '');
const dsSheets = () => readdirSync(join(SRC, DS)).filter((name) => name.endsWith('.css'));

function sourceFiles(dir: string, found: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) sourceFiles(path, found);
    else if (/\.tsx?$/.test(name) && !name.includes('.test.') && !name.includes('.generated.'))
      found.push(path);
  }
  return found;
}

/** Lines holding a hex colour, ignoring comments. */
function hexLines(text: string): string[] {
  return withoutComments(text)
    .split('\n')
    .filter((line) => !line.trim().startsWith('//') && HEX_COLOUR.test(line));
}

/** Every declaration of a property in a sheet, as its value (multi-line values joined). */
function declarations(css: string, property: string): string[] {
  const pattern = new RegExp(`(?:^|[;{\\s])${property}\\s*:\\s*([^;}]+)`, 'g');
  return [...withoutComments(css).matchAll(pattern)].map((m) =>
    (m[1] ?? '').replace(/\s+/g, ' ').trim(),
  );
}

/** A corner value made only of shared sizes, zero, a circle, or what the parent has. */
function sharedCorner(value: string): boolean {
  return /^(?:var\(--r-[a-z]+\)|0|50%|inherit|999px)$/.test(value);
}
/** A small inner piece: every corner 8 or under (chips inside a control, tiny marks). */
function innerCorner(value: string): boolean {
  const parts = value.split(' ');
  return parts.every((p) => /^\d+px$/.test(p) && Number.parseInt(p, 10) <= 8);
}

describe('design tokens', () => {
  it('tokens.css starts with the stamp the sync script writes (version and commit)', () => {
    const first = read('styles/tokens.css').split('\n')[0];
    expect(first).toMatch(
      /^\/\* Synced from console-at-rest v\d+\.\d+ @ [0-9a-f]{7,}\. Do not edit: run scripts\/sync-design-tokens\.cjs\. \*\/$/,
    );
  });

  it("only the shared values and the app's own sheets are left: the old sheets are gone", () => {
    expect(readdirSync(join(SRC, 'styles')).sort()).toEqual(['ds', 'fonts.css', 'tokens.css']);
  });

  it('fonts.css contains no colour', () => {
    expect(hexLines(read('styles/fonts.css'))).toEqual([]);
  });

  it("the app's sheets (styles/ds) contain no raw colour: no hex, rgb(), hsl() or the like", () => {
    for (const name of dsSheets()) {
      const lines = withoutComments(read(`${DS}/${name}`))
        .split('\n')
        .filter((line) => RAW_COLOUR.test(line));
      expect(lines, name).toEqual([]);
    }
  });

  it('no source file contains a hex colour', () => {
    const offenders = sourceFiles(SRC)
      .filter((file) => hexLines(readFileSync(file, 'utf8')).length > 0)
      .map((file) => relative(SRC, file));
    expect(offenders, 'Use a shared value from tokens.css instead').toEqual([]);
  });

  it('the colour checks themselves catch a colour and ignore comments', () => {
    expect(hexLines("const c = '#0B6BCB';")).toHaveLength(1);
    expect(hexLines('a { color: #fff; }')).toHaveLength(1);
    expect(hexLines('/* #0B6BCB in a comment */\n// #fff too\nconst ok = 1;')).toEqual([]);
    expect(RAW_COLOUR.test('box-shadow: 0 1px 2px rgba(20, 25, 40, 0.14);')).toBe(true);
    expect(RAW_COLOUR.test('background: color-mix(in srgb, var(--fg) 8%, transparent);')).toBe(
      false,
    );
  });

  it('corners are one of the shared sizes, a small inner piece, or a listed one-off', () => {
    const offences: string[] = [];
    const used = new Set<string>();
    for (const name of dsSheets()) {
      for (const value of declarations(read(`${DS}/${name}`), 'border-radius')) {
        if (sharedCorner(value) || innerCorner(value)) continue;
        const key = `${name}|${value}`;
        if (key in CORNER_ONE_OFFS) used.add(key);
        else offences.push(key);
      }
    }
    expect(
      offences,
      'Use var(--r-sm|ctl|panel|sheet), or list the one-off with its reason',
    ).toEqual([]);
    // The list may only shrink: an entry nothing uses any more must go.
    expect(Object.keys(CORNER_ONE_OFFS).filter((key) => !used.has(key))).toEqual([]);
  });

  it('shadows come from the shared values (or are a ring drawn in a shared colour)', () => {
    for (const name of dsSheets()) {
      const raw = declarations(read(`${DS}/${name}`), 'box-shadow').filter(
        (value) => value !== 'none' && !value.includes('var(--'),
      );
      expect(raw, name).toEqual([]);
    }
  });

  it('layers use the shared order; a bare number is only the order inside one piece (3 or under)', () => {
    for (const name of dsSheets()) {
      const raw = declarations(read(`${DS}/${name}`), 'z-index').filter(
        (value) => !value.includes('var(--z-') && !/^-?[0-3]$/.test(value),
      );
      expect(raw, name).toEqual([]);
    }
  });

  it('changes use the shared speeds; only a looping animation (a spinner, a pulse) keeps its own period', () => {
    const SECONDS = /(?<![\w-])\d*\.?\d+m?s\b/;
    for (const name of dsSheets()) {
      const css = read(`${DS}/${name}`);
      const transitions = [
        ...declarations(css, 'transition'),
        ...declarations(css, 'transition-duration'),
      ].filter((value) => SECONDS.test(value.replace(/var\([^)]*\)/g, '')));
      expect(transitions, `${name}: transitions`).toEqual([]);
      const animations = [
        ...declarations(css, 'animation'),
        ...declarations(css, 'animation-duration'),
      ].filter(
        (value) => SECONDS.test(value.replace(/var\([^)]*\)/g, '')) && !/\binfinite\b/.test(value),
      );
      expect(animations, `${name}: animations that run once`).toEqual([]);
    }
  });

  it('every variable the sheets read is defined in a sheet or set from a script', () => {
    const sheets = [
      read('styles/fonts.css'),
      read('styles/tokens.css'),
      ...dsSheets().map((n) => read(`${DS}/${n}`)),
    ].join('\n');
    const used = new Set([...sheets.matchAll(/var\(\s*(--[a-zA-Z0-9-]+)/g)].map((m) => m[1]));
    const defined = new Set([...sheets.matchAll(/(--[a-zA-Z0-9-]+)\s*:/g)].map((m) => m[1]));
    const missing = [...used].filter(
      (name) => !defined.has(name) && !SET_FROM_SCRIPT.has(name ?? ''),
    );
    expect(missing.sort()).toEqual([]);
  });
});
