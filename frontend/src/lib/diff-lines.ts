import type { VersionDiff } from '../api/filesystem';

export interface DiffRow {
  kind: 'removed' | 'added';
  text: string;
}

/**
 * The rows to draw for a version comparison: the lines only in the older version (removed) first, then the lines only in the
 * newer one (added). The server compares by line position, so these are the lines that differ, not a unified patch.
 */
export function diffRows(diff: VersionDiff): DiffRow[] {
  return [
    ...diff.removed_lines.map<DiffRow>((text) => ({ kind: 'removed', text })),
    ...diff.added_lines.map<DiffRow>((text) => ({ kind: 'added', text })),
  ];
}

/** "3 added, 1 removed" (or "No differences"). */
export function diffSummary(diff: VersionDiff): string {
  const { lines_added: added, lines_removed: removed } = diff.stats;
  // The server compares line by line and skips blank lines, so this is not a promise the files are identical.
  if (added === 0 && removed === 0) return 'No differing lines';
  return `${added} added, ${removed} removed`;
}
