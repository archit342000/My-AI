import { describe, expect, it } from 'vitest';
import { iconPaths, type IconName } from './icon-paths';

describe('iconPaths', () => {
  it('gives the drawing of an app icon and of a workspace icon', () => {
    expect(iconPaths('close')).toBeTruthy();
    expect(iconPaths('rocket')).toBeTruthy();
  });

  it('knows only its own names, not ones every object carries', () => {
    for (const name of ['constructor', 'toString', '__proto__', 'no-such-icon']) {
      expect(iconPaths(name as IconName)).toBeUndefined();
    }
  });
});
