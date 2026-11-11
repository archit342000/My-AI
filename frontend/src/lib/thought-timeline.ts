/**
 * The entries of a thought box, built from a turn's steps. Pure, so it is unit-tested.
 * Main-agent text is the answer bubble and is not part of the box; sub-agent steps are grouped.
 */
import type { Step } from './chat-model';
import { agentLabel } from './labels';

export type TimelineItem =
  | { kind: 'reasoning'; key: string; text: string }
  | { kind: 'text'; key: string; text: string }
  | { kind: 'event'; key: string; text: string }
  /** One tool call with its answer; `result` is null while the tool is still running. */
  | { kind: 'tool'; key: string; name: string; args: string; result: string | null }
  | { kind: 'group'; key: string; label: string; items: TimelineItem[] };

function itemsOf(step: Step, key: string): TimelineItem[] {
  switch (step.kind) {
    case 'reasoning':
      return step.text ? [{ kind: 'reasoning', key, text: step.text }] : [];
    case 'text':
      // Only a sub-agent's text is shown here; the main agent's text is the bubble.
      return step.agent !== null && step.text ? [{ kind: 'text', key, text: step.text }] : [];
    case 'event':
      return step.text ? [{ kind: 'event', key, text: step.text }] : [];
    case 'tool':
      return [{ kind: 'tool', key, name: step.name, args: step.args, result: step.result }];
  }
}

/** The entries to show, in step order; consecutive steps of one sub-agent form one group. */
export function timelineOf(steps: Step[]): TimelineItem[] {
  const out: TimelineItem[] = [];
  let i = 0;
  while (i < steps.length) {
    const step = steps[i];
    if (!step) break;
    if (step.agent === null) {
      out.push(...itemsOf(step, String(i)));
      i += 1;
      continue;
    }
    const agent = step.agent;
    const start = i;
    const items: TimelineItem[] = [];
    for (let next = steps[i]; next && next.agent === agent; next = steps[i]) {
      items.push(...itemsOf(next, String(i)));
      i += 1;
    }
    if (items.length > 0)
      out.push({ kind: 'group', key: `g${start}`, label: agentLabel(agent), items });
  }
  return out;
}

/** The live status line: the latest activity, an event or a tool still running, else nothing. */
export function statusOf(steps: Step[], toolLabel: (name: string) => string): string | null {
  for (const s of [...steps].reverse()) {
    if (s.kind === 'event' && s.text) return s.text;
    if (s.kind === 'tool' && s.result === null) return toolLabel(s.name);
  }
  return null;
}

/** How many tool calls a timeline holds, counting those inside sub-agent groups. */
export function toolCount(items: TimelineItem[]): number {
  return items.reduce(
    (n, item) => n + (item.kind === 'tool' ? 1 : item.kind === 'group' ? toolCount(item.items) : 0),
    0,
  );
}

/** "3 tools used", "1 tool used", or "" when no tool was called. */
export function toolSummary(items: TimelineItem[]): string {
  const n = toolCount(items);
  return n === 0 ? '' : `${n} ${n === 1 ? 'tool' : 'tools'} used`;
}

/**
 * What a tool was asked, in a few words for its row: the first plain value among its arguments
 * (a path, a search, a command). Empty while the arguments are still arriving or hold nothing plain.
 */
export function toolDetail(args: string): string {
  let parsed: unknown;
  try {
    parsed = JSON.parse(args);
  } catch {
    return '';
  }
  if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) return '';
  for (const value of Object.values(parsed)) {
    if (typeof value === 'string' && value.trim()) return value.trim().split('\n')[0] ?? '';
    if (typeof value === 'number') return String(value);
  }
  return '';
}

/** A tool's answer that reports a failure in the server's usual wording. */
export function toolFailed(result: string | null): boolean {
  return result !== null && /^\s*(error\b|\{\s*"error")/i.test(result);
}
