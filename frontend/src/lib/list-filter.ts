/** Search, tag filter and sort for the memory and skills lists (client-side: the lists are small). */
import type { Preference, Skill } from '../api/settings';
import { memoryTagLabel } from './labels';

export type PreferenceSort = 'newest' | 'oldest';

export interface PreferenceFilter {
  query: string;
  /** A tag label (as `memoryTagLabel` shows it) to keep, or '' for all tags. */
  tag: string;
  sort: PreferenceSort;
}

const matches = (haystack: string, needle: string) => haystack.toLowerCase().includes(needle);

/** Memory entries filtered by text and tag, ordered by time. */
export function filterPreferences(items: Preference[], filter: PreferenceFilter): Preference[] {
  const query = filter.query.trim().toLowerCase();
  const kept = items.filter(
    (item) =>
      (!filter.tag || memoryTagLabel(item.tag) === filter.tag) &&
      (!query || matches(item.content, query)),
  );
  const direction = filter.sort === 'oldest' ? 1 : -1;
  return [...kept].sort((a, b) => direction * (a.timestamp - b.timestamp));
}

/** Skills whose name or description contains the text. */
export function filterSkills(items: Skill[], query: string): Skill[] {
  const needle = query.trim().toLowerCase();
  if (!needle) return items;
  return items.filter((s) => matches(s.name, needle) || matches(s.description, needle));
}

/** The distinct tag labels present in a list, in the order they first appear (`preference` and `preferences` share one). */
export function tagsOf(items: Preference[]): string[] {
  return Array.from(
    new Set(
      items
        .map((item) => item.tag)
        .filter(Boolean)
        .map(memoryTagLabel),
    ),
  );
}
