/**
 * Pure reducer for the completions stream (OpenAI-style `choices[0].delta` plus the app's
 * extra events). Mirrors the legacy `sendMessage` read loop in `static/script.js`.
 * The turn is an ordered step list, the same shape `toTurns` builds from stored messages.
 */
import type { AgentRun } from '../../api/types';
import type { Step } from '../../lib/chat-model';
import {
  CLARIFICATION_TOOL,
  parseClarification,
  type ClarificationRequest,
} from '../../lib/clarification';

export interface LiveTurn {
  steps: Step[];
  model: string | null;
  redactNotice: string | null;
  /** Steps saved at each main-agent `event`, used to roll back a failed attempt on `redact`. */
  snapshot: Step[];
  /** A question the turn is waiting on (see `lib/clarification.ts`); null when nothing is pending. */
  pendingRequest: ClarificationRequest | null;
}

export function emptyLiveTurn(): LiveTurn {
  return { steps: [], model: null, redactNotice: null, snapshot: [], pendingRequest: null };
}

interface ToolCallDelta {
  id?: string;
  index?: number;
  function?: { name?: string; arguments?: string };
}

interface ToolResultDelta {
  tool_call_id?: string;
  content?: string;
  /** Milliseconds the call took (0 when it was refused). */
  duration_ms?: number;
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
  /** Sent once, after a turn that finished normally. */
  turn?: { duration_ms?: number };
  /** A helper run starting, changing activity or ending (the helpers card is a follow-up). */
  agent_run?: AgentRun;
  choices?: Array<{ delta?: Delta }>;
}

export class StreamError extends Error {}

export function applyChunk(turn: LiveTurn, chunk: StreamChunk): LiveTurn {
  if (chunk.error) throw new StreamError(chunk.error);
  const next = chunk.model ? { ...turn, model: chunk.model } : turn;

  if (chunk.__redact__) {
    return {
      ...next,
      steps: next.snapshot,
      // The server writes three dots; the app writes the ellipsis as one character.
      redactNotice: (chunk.message ?? 'Correcting the formatting…').replace(/\.{3}$/, '…'),
      pendingRequest: null,
    };
  }

  const delta = chunk.choices?.[0]?.delta;
  if (!delta) return next;

  const agent = chunk.parent_type && chunk.parent_type !== 'main' ? chunk.parent_type : null;

  if (delta.role === 'event') {
    // Events are activity labels, not answer text (legacy `continue`s after them).
    const text = delta.content ?? '';
    // An empty event adds no step, like the saved path; the snapshot still moves to this point.
    const steps = text ? addStep(next.steps, { kind: 'event', text, agent }, agent) : next.steps;
    return { ...next, steps, snapshot: agent === null ? steps : next.snapshot };
  }
  let steps = next.steps;
  let pendingRequest = next.pendingRequest;
  if (delta.reasoning_content)
    steps = appendText(steps, 'reasoning', delta.reasoning_content, agent);
  if (delta.content) steps = appendText(steps, 'text', delta.content, agent);
  if (delta.tool_calls?.length) {
    // The server repeats a `request_clarification` call (same id) once its callback is registered: that chunk
    // is the pending request. It never changes the step it repeats (a code-runner approval repeats the run's id).
    const repeats = delta.tool_calls.filter((d) => isRepeatedRequest(steps, d));
    for (const d of repeats) {
      pendingRequest = parseClarification(d.id ?? '', d.function?.arguments ?? '');
    }
    const rest = delta.tool_calls.filter((d) => !repeats.includes(d));
    if (rest.length) steps = mergeToolCalls(steps, rest, agent);
  }
  if (delta.tool_result) {
    steps = attachResult(steps, delta.tool_result, agent);
    // The answer arrived (here or in another tab): the question is closed.
    const answered = delta.tool_result.tool_call_id;
    if (pendingRequest && answered === pendingRequest.id) pendingRequest = null;
  }
  if (steps === next.steps && pendingRequest === next.pendingRequest) return next;
  return { ...next, steps, pendingRequest };
}

/** A `request_clarification` call whose id already belongs to a step: the repeat the server sends when it waits. */
function isRepeatedRequest(steps: Step[], d: ToolCallDelta): boolean {
  return (
    d.function?.name === CLARIFICATION_TOOL &&
    Boolean(d.id) &&
    steps.some((s) => s.kind === 'tool' && s.id === d.id)
  );
}

/**
 * Where a step by `agent` goes. The main agent appends. A sub-agent's steps go directly after the
 * main-agent tool step that is still running (the first without a result; tools run one at a time),
 * after that tool's earlier sub-agent steps; with no running tool they are appended.
 */
function insertionIndex(steps: Step[], agent: string | null): number {
  if (agent === null) return steps.length;
  const running = steps.findIndex(
    (s) => s.kind === 'tool' && s.agent === null && s.result === null,
  );
  if (running === -1) return steps.length;
  let end = running + 1;
  while (end < steps.length && steps[end]?.agent !== null) end++;
  return end;
}

function addStep(steps: Step[], step: Step, agent: string | null): Step[] {
  const at = insertionIndex(steps, agent);
  return [...steps.slice(0, at), step, ...steps.slice(at)];
}

/** Extends the last step of the same kind and agent in the block, else starts a new step. */
function appendText(
  steps: Step[],
  kind: 'reasoning' | 'text',
  text: string,
  agent: string | null,
): Step[] {
  const at = insertionIndex(steps, agent);
  const prev = steps[at - 1];
  if (prev && prev.kind === kind && prev.agent === agent) {
    const out = steps.slice();
    out[at - 1] = { ...prev, text: prev.text + text };
    return out;
  }
  return [...steps.slice(0, at), { kind, text, agent }, ...steps.slice(at)];
}

/**
 * Tool-call fragments: a new id starts a call; later fragments append arguments by id, or by index
 * among the tool steps added since the last non-tool step when they carry no id.
 */
export function mergeToolCalls(
  steps: Step[],
  deltas: ToolCallDelta[],
  agent: string | null = null,
): Step[] {
  let out = steps.slice();
  for (const d of deltas) {
    const id = d.id ?? '';
    let idx = id ? out.findIndex((s) => s.kind === 'tool' && s.agent === agent && s.id === id) : -1;
    if (idx === -1 && !id && typeof d.index === 'number') {
      const run: number[] = [];
      for (let i = out.length - 1; i >= 0; i--) {
        const s = out[i];
        if (!s) break;
        // A finished call belongs to an earlier round: a new round's fragments never continue it.
        if (s.kind === 'tool' && s.agent === agent && s.result === null) run.unshift(i);
        else if (s.agent === agent || run.length > 0) break;
      }
      idx = run[d.index] ?? -1;
    }
    if (idx === -1) {
      out = addStep(
        out,
        {
          kind: 'tool',
          id,
          name: d.function?.name ?? 'tool',
          args: d.function?.arguments ?? '',
          result: null,
          agent,
        },
        agent,
      );
    } else {
      const existing = out[idx];
      if (existing?.kind !== 'tool') continue;
      out[idx] = {
        ...existing,
        name: d.function?.name && existing.name === 'tool' ? d.function.name : existing.name,
        args: existing.args + (d.function?.arguments ?? ''),
      };
    }
  }
  return out;
}

/** Attaches a tool result to its call, or to the newest call of the same agent still waiting. */
export function attachResult(
  steps: Step[],
  result: ToolResultDelta,
  agent: string | null = null,
): Step[] {
  const out = steps.slice();
  let idx = result.tool_call_id
    ? out.findIndex((s) => s.kind === 'tool' && s.id === result.tool_call_id)
    : -1;
  if (idx === -1) {
    for (let i = out.length - 1; i >= 0; i--) {
      const s = out[i];
      if (s?.kind === 'tool' && s.agent === agent && s.result === null) {
        idx = i;
        break;
      }
    }
  }
  if (idx === -1) return out;
  const target = out[idx];
  if (target?.kind === 'tool') out[idx] = { ...target, result: result.content ?? '' };
  return out;
}
