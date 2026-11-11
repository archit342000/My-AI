import { describe, expect, it } from 'vitest';
import { FOLD_CHARS, FOLD_LINES, isLongMessage, splitSkill } from './user-text';

describe('isLongMessage', () => {
  it('folds by length or by number of lines', () => {
    expect(isLongMessage('short')).toBe(false);
    expect(isLongMessage('x'.repeat(FOLD_CHARS))).toBe(false);
    expect(isLongMessage('x'.repeat(FOLD_CHARS + 1))).toBe(true);
    expect(isLongMessage(Array(FOLD_LINES).fill('a').join('\n'))).toBe(false);
    expect(
      isLongMessage(
        Array(FOLD_LINES + 1)
          .fill('a')
          .join('\n'),
      ),
    ).toBe(true);
  });
});

describe('splitSkill', () => {
  it('takes a slash command from the very start', () => {
    expect(splitSkill('/summarise-paper the attached file')).toEqual({
      skill: '/summarise-paper',
      rest: 'the attached file',
    });
    expect(splitSkill('/help')).toEqual({ skill: '/help', rest: '' });
    expect(splitSkill('/fix\nthis code')).toEqual({ skill: '/fix', rest: '\nthis code' });
  });

  it('leaves ordinary text, paths and mid-sentence slashes alone', () => {
    for (const text of ['hello /skill', '/usr/bin/env python', '/ alone', '/9lives', '']) {
      expect(splitSkill(text)).toEqual({ skill: null, rest: text });
    }
  });
});
