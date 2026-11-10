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
  | { kind: 'call'; key: string; name: string; args: string; running: boolean }
  | { kind: 'result'; key: string; name: string; result: string }
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
    case 'tool': {
      const call: TimelineItem = {
        kind: 'call',
        key: `${key}:call`,
        name: step.name,
        args: step.args,
        running: step.result === null,
      };
      return step.result === null
        ? [call]
        : [call, { kind: 'result', key: `${key}:result`, name: step.name, result: step.result }];
    }
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
    (n, item) => n + (item.kind === 'call' ? 1 : item.kind === 'group' ? toolCount(item.items) : 0),
    0,
  );
}

/** "3 tools used", "1 tool used", or "" when no tool was called. */
export function toolSummary(items: TimelineItem[]): string {
  const n = toolCount(items);
  return n === 0 ? '' : `${n} ${n === 1 ? 'tool' : 'tools'} used`;
}
