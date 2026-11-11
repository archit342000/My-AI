import type { Artifact } from '../../api/filesystem';
import { artifactPath, isDirectoryEntry } from './artifact-tree';

export interface SearchHit {
  artifact: Artifact;
  path: string;
  /** The first line of the file's text that holds the words, when its text is loaded. */
  line?: { number: number; text: string };
}

const SNIPPET_MAX = 160;

function firstLine(content: string, needle: string): SearchHit['line'] {
  const lines = content.split('\n');
  for (let i = 0; i < lines.length; i++) {
    const raw = (lines[i] ?? '').trim();
    const at = raw.toLowerCase().indexOf(needle);
    if (at === -1) continue;
    // A very long line is cut around the match, so the words searched for stay in view.
    const start = Math.max(0, Math.min(at - 40, raw.length - SNIPPET_MAX));
    const text =
      raw.length > SNIPPET_MAX
        ? `${start > 0 ? '…' : ''}${raw.slice(start, start + SNIPPET_MAX)}…`
        : raw;
    return { number: i + 1, text };
  }
  return undefined;
}

/**
 * Files whose name or text holds the words. Names are always searched; text is searched for the
 * files whose contents have been loaded (`contents`, by file id). Name matches come first.
 */
export function searchFiles(
  items: readonly Artifact[],
  contents: ReadonlyMap<string, string>,
  query: string,
): SearchHit[] {
  const needle = query.trim().toLowerCase();
  if (!needle) return [];
  const byName: SearchHit[] = [];
  const byText: SearchHit[] = [];
  for (const artifact of items) {
    if (isDirectoryEntry(artifact)) continue;
    const path = artifactPath(artifact);
    const text = contents.get(artifact.id);
    const line = text === undefined ? undefined : firstLine(text, needle);
    if (path.toLowerCase().includes(needle)) byName.push({ artifact, path, line });
    else if (line) byText.push({ artifact, path, line });
  }
  const order = (a: SearchHit, b: SearchHit) =>
    a.path.localeCompare(b.path, undefined, { sensitivity: 'base', numeric: true });
  return [...byName.sort(order), ...byText.sort(order)];
}
