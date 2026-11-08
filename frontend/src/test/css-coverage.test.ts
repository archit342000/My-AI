import { describe, expect, it } from 'vitest';
import { classNamesInSource, classSelectorsInCss, listFiles, readSrc, SRC_DIR } from './source-scan';

/**
 * Guard: every class name written in TSX must have a CSS rule, so elements never fall back to
 * browser defaults (white native buttons, unstyled inputs). See plan F-53 and §2 root cause 1.
 */

/** Pure JavaScript hooks: class names used for querying or state, never styled. */
const JS_HOOKS = new Set<string>([
  // State markers set by the stream and read by the markup/tests, not styled on their own.
  'bot',
  'streaming',
]);

/**
 * Known orphans that are still unstyled. Each one must be removed as soon as a rule exists;
 * the test fails if an entry becomes styled, so this list can only shrink.
 */
const TODO_UNSTYLED = new Set<string>([
  'bot-message-footer',
  'chat-row',
  'copy-msg-btn',
  'delete-msg-btn',
  'edit-msg-btn',
  'folder-chevron-wrapper',
  'full-width-reasoning',
  'message-content-wrapper',
  'message-text-wrapper',
  'raw-text-content',
  'retry-msg-btn',
  'sidebar-context-menu-header',
  'thought-section-wrapper',
  'thought-text',
  'title-text',
  'validation-fixing',
  'workspace-view',
]);

function cssSelectors(): Set<string> {
  const all = new Set<string>();
  for (const file of listFiles(`${SRC_DIR}/styles`, /\.css$/)) {
    for (const name of classSelectorsInCss(readSrc(file))) all.add(name);
  }
  return all;
}

function tsxClassNames(): Map<string, string[]> {
  const usage = new Map<string, string[]>();
  for (const file of listFiles(SRC_DIR, /\.tsx$/)) {
    if (file.endsWith('.test.tsx')) continue;
    for (const name of classNamesInSource(readSrc(file))) {
      const list = usage.get(name) ?? [];
      list.push(file);
      usage.set(name, list);
    }
  }
  return usage;
}

describe('css coverage', () => {
  const css = cssSelectors();
  const usage = tsxClassNames();

  it('finds class names in both sources (scanner sanity)', () => {
    expect(css.has('btn-primary')).toBe(true);
    expect(usage.has('btn-primary')).toBe(true);
  });

  it('every TSX class name has a CSS rule', () => {
    const orphans = [...usage.keys()]
      .filter((name) => !css.has(name) && !JS_HOOKS.has(name) && !TODO_UNSTYLED.has(name))
      .map((name) => `${name} (${usage.get(name)!.join(', ')})`)
      .sort();
    expect(orphans, `Unstyled classes: add a rule to styles/components.css`).toEqual([]);
  });

  it('TODO_UNSTYLED only lists classes that are still unstyled and still used', () => {
    const nowStyled = [...TODO_UNSTYLED].filter((name) => css.has(name));
    expect(nowStyled, 'Remove these from TODO_UNSTYLED (now styled)').toEqual([]);
    const unused = [...TODO_UNSTYLED].filter((name) => !usage.has(name));
    expect(unused, 'Remove these from TODO_UNSTYLED (no longer used)').toEqual([]);
  });
});
