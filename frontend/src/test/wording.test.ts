import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative, resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

// Guards the wording rules of the rule book (Part 9) that a scan can check.

const SRC = resolve(__dirname, '..');

function sources(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return name === 'dev' ? [] : sources(path);
    return /\.tsx?$/.test(name) && !/\.test\.tsx?$/.test(name) && !name.includes('.generated.')
      ? [path]
      : [];
  });
}

/** Every place a rule is broken, as `file:line: text`. */
function offences(pattern: RegExp): string[] {
  const found: string[] = [];
  for (const file of sources(SRC)) {
    readFileSync(file, 'utf8')
      .split('\n')
      .forEach((line, i) => {
        if (pattern.test(line)) found.push(`${relative(SRC, file)}:${i + 1}: ${line.trim()}`);
      });
  }
  return found;
}

describe('wording', () => {
  it('no button says Submit, OK, Yes or No: a button names what it does', () => {
    expect(offences(/>\s*(Submit|OK|Ok|Okay|Yes|No)\s*<\/(Button|button)>/)).toEqual([]);
    expect(offences(/(confirmLabel|actionLabel|label)=["'](Submit|OK|Ok|Okay|Yes|No)["']/)).toEqual(
      [],
    );
  });

  it('a confirming pop-up names the thing it acts on, not just "Delete" or "Confirm"', () => {
    expect(offences(/confirmLabel=["'](Delete|Remove|Confirm|Reset|Discard|Continue)["']/)).toEqual(
      [],
    );
  });

  it('writes the ellipsis as one character, never three dots', () => {
    // Text between tags or inside a quoted string that ends in three dots.
    expect(
      offences(/[A-Za-z]\.\.\.(['"`<]|\s*$)/).filter((l) => !/^\S+:\d+:\s*(\/\/|\*|\/\*)/.test(l)),
    ).toEqual([]);
  });

  it('keeps the words the rule book rules out away from what people read', () => {
    const words = /(['"`>][^'"`<]*)\b(successfully|oops|please wait|are you sure)\b/i;
    expect(offences(words).filter((l) => !/^\S+:\d+:\s*(\/\/|\*|\/\*)/.test(l))).toEqual([]);
  });

  it('formats dates and times in one place (lib/format-time.ts), not with the browser defaults', () => {
    expect(offences(/\.toLocale(Date|Time)String\(|\.toLocaleString\(\s*\)/)).toEqual([]);
  });

  it('keeps Title Case out of button and menu labels', () => {
    // Two or more capitalised words in a label, title or button text ("New Chat", "Save Changes").
    const titled =
      /(label|title|confirmLabel|actionLabel|placeholder)=["'][A-Z][a-z]+( [A-Z][a-z]+)+["']/;
    const proper = /My AI|GitHub|Top P/;
    expect(offences(titled).filter((l) => !proper.test(l))).toEqual([]);
  });
});
