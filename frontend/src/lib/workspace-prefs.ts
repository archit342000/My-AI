/**
 * Workspace UI state persisted by the legacy app under the `chatWorkspaces` localStorage key:
 * a JSON array of `{ name, expanded, ... }`. Kept in the same format so existing browsers keep
 * their expanded/collapsed state (the admin keeps that key; other users get `chatWorkspaces:<userId>`, see
 * `nsKey`). Only the `expanded` flag is written here.
 */
import { nsKey } from './user-storage';

export const WORKSPACE_PREFS_KEY = 'chatWorkspaces';

interface StoredWorkspace {
  name: string;
  expanded?: boolean;
  [extra: string]: unknown;
}

function readAll(): StoredWorkspace[] {
  const key = nsKey(WORKSPACE_PREFS_KEY); // outside the try: a missing user is a bug to surface
  try {
    const parsed = JSON.parse(localStorage.getItem(key) || '[]') as unknown;
    return Array.isArray(parsed) ? (parsed as StoredWorkspace[]) : [];
  } catch {
    return [];
  }
}

/** Expanded flag for a workspace name. Defaults to expanded when nothing is stored. */
export function isWorkspaceExpanded(name: string): boolean {
  const entry = readAll().find((w) => w.name === name);
  return entry?.expanded ?? true;
}

export function setWorkspaceExpanded(name: string, expanded: boolean): void {
  const all = readAll();
  const entry = all.find((w) => w.name === name);
  if (entry) entry.expanded = expanded;
  else all.push({ name, expanded });
  localStorage.setItem(nsKey(WORKSPACE_PREFS_KEY), JSON.stringify(all));
}
