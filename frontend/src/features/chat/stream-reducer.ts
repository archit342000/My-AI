/**
 * Pure reducer for the completions stream (OpenAI-style `choices[0].delta` plus the app's
 * extra events). Mirrors the legacy `sendMessage` read loop in `static/script.js`.
 */
import type { ToolActivity } from '../../lib/chat-model';

export interface LiveTurn {
  content: string;
  reasoning: string;
  tools: ToolActivity[];
  events: string[];
  model: string | null;
  redactNotice: string | null;
  /** Count of sub-agent deltas; their content is not shown in the main transcript yet. */
  subAgentDeltas: number;
  /** Snapshot taken at each `event`, used to roll back a failed attempt on `redact`. */
  snapshot: { content: string; reasoning: string; toolCount: number };
}

export function emptyLiveTurn(): LiveTurn {
  return {
    content: '',
    reasoning: '',
    tools: [],
    events: [],
    model: null,
    redactNotice: null,
    subAgentDeltas: 0,
    snapshot: { content: '', reasoning: '', toolCount: 0 },
  };
}

interface ToolCallDelta {
  id?: string;
  index?: number;
  function?: { name?: string; arguments?: string };
}

interface ToolResultDelta {
  tool_call_id?: string;
  content?: string;
}

interface Delta {
  content?: string | null;
  reasoning_content?: string | null;
  tool_calls?: ToolCallDelta[] | null;
  tool_result?: ToolResultDelta | null;
  role?: string;
}

/** One parsed stream object. Unknown keys are ignored. */
export interface StreamChunk {
  error?: string;
  model?: string;
  type?: string;
  __redact__?: boolean;
  message?: string;
  parent_type?: string;
  choices?: Array<{ delta?: Delta }>;
}

export class StreamError extends Error {}

export function applyChunk(turn: LiveTurn, chunk: StreamChunk): LiveTurn {
  if (chunk.error) throw new StreamError(chunk.error);
  let next = chunk.model ? { ...turn, model: chunk.model } : turn;

  if (chunk.__redact__) {
    return {
      ...next,
      content: next.snapshot.content,
      reasoning: next.snapshot.reasoning,
      tools: next.tools.slice(0, next.snapshot.toolCount),
      redactNotice: chunk.message ?? 'Correcting formatting...',
    };
  }

  const delta = chunk.choices?.[0]?.delta;
  if (!delta) return next;

  const isSubAgent = Boolean(chunk.parent_type && chunk.parent_type !== 'main');
  if (isSubAgent) return { ...next, subAgentDeltas: next.subAgentDeltas + 1 };

  if (delta.role === 'event') {
    // Events are activity labels, not answer text (legacy `continue`s after them).
    return {
      ...next,
      events: [...next.events, delta.content ?? ''],
      snapshot: { content: next.content, reasoning: next.reasoning, toolCount: next.tools.length },
    };
  }
  if (delta.reasoning_content) next = { ...next, reasoning: next.reasoning + delta.reasoning_content };
  if (delta.content) next = { ...next, content: next.content + delta.content };
  if (delta.tool_calls?.length) next = { ...next, tools: mergeToolCalls(next.tools, delta.tool_calls) };
  if (delta.tool_result) next = { ...next, tools: attachResult(next.tools, delta.tool_result) };
  return next;
}

/** Tool-call fragments: a new id starts a call; later fragments append arguments by id or index. */
export function mergeToolCalls(tools: ToolActivity[], deltas: ToolCallDelta[]): ToolActivity[] {
  const out = tools.slice();
  for (const d of deltas) {
    const id = d.id ?? '';
    let idx = id ? out.findIndex((t) => t.id === id) : -1;
    if (idx === -1 && !id && typeof d.index === 'number') idx = d.index < out.length ? d.index : -1;
    if (idx === -1) {
      out.push({ id, name: d.function?.name ?? 'tool', args: d.function?.arguments ?? '', result: null });
    } else {
      const existing = out[idx]!;
      out[idx] = {
        ...existing,
        name: d.function?.name && existing.name === 'tool' ? d.function.name : existing.name,
        args: existing.args + (d.function?.arguments ?? ''),
      };
    }
  }
  return out;
}

/** Attaches a tool result to its call, or to the most recent call still waiting for a result. */
export function attachResult(tools: ToolActivity[], result: ToolResultDelta): ToolActivity[] {
  const out = tools.slice();
  let idx = result.tool_call_id ? out.findIndex((t) => t.id === result.tool_call_id) : -1;
  if (idx === -1) {
    for (let i = out.length - 1; i >= 0; i--) {
      if (out[i]!.result === null) {
        idx = i;
        break;
      }
    }
  }
  if (idx === -1) return out;
  out[idx] = { ...out[idx]!, result: result.content ?? '' };
  return out;
}
