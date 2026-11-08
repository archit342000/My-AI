import { TOOL_LABELS } from './tool-labels.generated';

/** Display name for a tool: the curated label, else the raw name title-cased (`web_fetch` → `Web Fetch`). */
export function friendlyToolName(name: string): string {
  const curated = TOOL_LABELS[name];
  if (curated) return curated;
  return name
    .split(/[_\s]+/)
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}
