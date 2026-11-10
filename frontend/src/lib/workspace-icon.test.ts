import { describe, expect, it } from 'vitest';
import { workspaceEmoji, workspaceIconName } from './workspace-icon';

describe('workspace icons', () => {
  it('uses the chosen icon, and the folder when none or an unknown one is set', () => {
    expect(workspaceIconName('rocket')).toBe('rocket');
    expect(workspaceIconName(null)).toBe('folder');
    expect(workspaceIconName('')).toBe('folder');
    expect(workspaceIconName('🚀')).toBe('folder');
  });

  it('an emoji from the old app is kept as it is', () => {
    expect(workspaceEmoji('🚀')).toBe('🚀');
    expect(workspaceEmoji('rocket')).toBeNull();
    expect(workspaceEmoji(undefined)).toBeNull();
  });
});
