import { TOOL_LABELS } from './tool-labels.generated';

/** Names that keep their capital wherever they stand. */
const PROPER = ['Google', 'GitHub', 'Python', 'JavaScript', 'SQL', 'URL', 'PDF', 'AI', 'MCP'];
const PROPER_BY_LOWER = new Map(PROPER.map((word) => [word.toLowerCase(), word]));

/** Only the first word and proper names carry a capital (rule book Part 9): "Read File" is "Read file". */
function sentenceCase(label: string): string {
  return label
    .split(' ')
    .map((word, i) => {
      const proper = PROPER_BY_LOWER.get(word.toLowerCase());
      if (proper) return proper;
      if (word.length > 1 && word === word.toUpperCase()) return word;
      return i === 0 ? word.charAt(0).toUpperCase() + word.slice(1) : word.toLowerCase();
    })
    .join(' ');
}

/** Display name for a tool: the curated label, else the raw name in words (`web_fetch` is "Web fetch"). */
export function friendlyToolName(name: string): string {
  const curated = TOOL_LABELS[name];
  if (curated) return sentenceCase(curated);
  return sentenceCase(
    name
      .split(/[_\s]+/)
      .filter(Boolean)
      .join(' '),
  );
}
