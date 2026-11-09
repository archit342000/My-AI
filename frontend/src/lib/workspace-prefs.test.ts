import { beforeEach, describe, expect, it } from 'vitest';
import { WORKSPACE_PREFS_KEY, isWorkspaceExpanded, setWorkspaceExpanded } from './workspace-prefs';
import { initUserStorage } from './user-storage';

describe('workspace prefs with per-user storage', () => {
  beforeEach(() => localStorage.clear());

  it('the admin keeps the existing key and format', () => {
    initUserStorage({ id: 'a1', role: 'admin' });
    localStorage.setItem(WORKSPACE_PREFS_KEY, JSON.stringify([{ name: 'w', expanded: false, color: 'red' }]));
    expect(isWorkspaceExpanded('w')).toBe(false);
    setWorkspaceExpanded('w', true);
    expect(JSON.parse(localStorage.getItem(WORKSPACE_PREFS_KEY) ?? '[]')).toEqual([{ name: 'w', expanded: true, color: 'red' }]);
  });

  it("users do not see each other's or the admin's workspace state", () => {
    localStorage.setItem(WORKSPACE_PREFS_KEY, JSON.stringify([{ name: 'w', expanded: false }]));
    initUserStorage({ id: 'u1', role: 'user' });
    expect(isWorkspaceExpanded('w')).toBe(true); // default, not the admin's collapsed state
    setWorkspaceExpanded('w', false);
    initUserStorage({ id: 'u2', role: 'user' });
    expect(isWorkspaceExpanded('w')).toBe(true);
    expect(localStorage.getItem(`${WORKSPACE_PREFS_KEY}:u1`)).toContain('"expanded":false');
    expect(JSON.parse(localStorage.getItem(WORKSPACE_PREFS_KEY) ?? '[]')).toEqual([{ name: 'w', expanded: false }]);
  });
});
