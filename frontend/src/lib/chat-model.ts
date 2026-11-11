/**
 * Converts stored messages into display turns. Pure, so it is unit-tested.
 * Tool results (role `tool`) are attached to the assistant tool call with the same id.
 */
import { parseContent } from './markdown/content';
import type { StoredMessage, StoredSubAgentRow } from '../api/types';
import type { UploadedFile } from '../api/completions';

export interface ToolActivity {
  id: string;
  name: string;
  args: string;
  result: string | null;
}

/**
 * One step of an assistant turn. `agent` is null for the main assistant and the agent name for
 * sub-agent steps. Live (stream reducer) and saved (`toTurns`) turns use the same shape.
 */
export type Step =
  | { kind: 'reasoning' | 'text' | 'event'; text: string; agent: string | null }
  | {
      kind: 'tool';
      id: string;
      name: string;
      args: string;
      result: string | null;
      agent: string | null;
    };

export type Turn =
  | {
      kind: 'user';
      id: string;
      text: string;
      images: string[];
      files: UploadedFile[];
      /** When it was sent, as the server stored it. */
      time?: number | string | null;
    }
  | {
      kind: 'assistant';
      /** First stored message id of the turn (stable React key). */
      id: string;
      /** Stored message ids of the turn, first row first; deleting the first removes the whole turn. */
      messageIds: string[];
      steps: Step[];
      model: string | null;
      /** When the reply was written (its last stored message). */
      time?: number | string | null;
    };

/** The answer: main-agent text steps, one paragraph each. */
export function turnText(steps: Step[]): string {
  return steps
    .filter((s) => s.kind === 'text' && s.agent === null)
    .map((s) => ('text' in s ? s.text : ''))
    .join('\n\n');
}

/** Reasoning of every agent, joined by newlines (the thought box shows it until it shows steps). */
export function turnReasoning(steps: Step[]): string {
  return steps
    .filter((s) => s.kind === 'reasoning')
    .map((s) => ('text' in s ? s.text : ''))
    .join('\n');
}

/** Tool calls of every agent with their results. */
export function turnTools(steps: Step[]): ToolActivity[] {
  const tools: ToolActivity[] = [];
  for (const s of steps) {
    if (s.kind === 'tool') tools.push({ id: s.id, name: s.name, args: s.args, result: s.result });
  }
  return tools;
}

/** The stored id that starts a turn; deleting it removes the whole turn on the server. */
export function firstMessageId(turn: Turn): string {
  return turn.kind === 'assistant' ? (turn.messageIds[0] ?? turn.id) : turn.id;
}

/** The text of the newest event step, or null. */
export function lastEvent(steps: Step[]): string | null {
  for (let i = steps.length - 1; i >= 0; i--) {
    const s = steps[i];
    if (s?.kind === 'event') return s.text;
  }
  return null;
}

const ABSENT = new Set(['', 'None', 'null', 'undefined']);

/** True when a stored field carries no value. */
export function isAbsent(value: unknown): boolean {
  return (
    value === null || value === undefined || (typeof value === 'string' && ABSENT.has(value.trim()))
  );
}

function clean(value: unknown): string {
  return isAbsent(value) ? '' : String(value);
}

interface ContentPart {
  type?: string;
  text?: string;
  image_url?: { url?: string };
}

/** Parses user content: plain text, or a JSON array of text and image_url parts. */
export function parseUserContent(raw: string): { text: string; images: string[] } {
  const trimmed = raw.trim();
  if (trimmed.startsWith('[')) {
    try {
      const parts = JSON.parse(trimmed) as ContentPart[];
      if (Array.isArray(parts)) {
        const text = parts
          .filter((p) => p.type === 'text' && typeof p.text === 'string')
          .map((p) => p.text as string)
          .join('\n');
        const images = parts
          .filter((p) => p.type === 'image_url' && typeof p.image_url?.url === 'string')
          .map((p) => p.image_url?.url as string);
        return { text, images };
      }
    } catch {
      /* not JSON: treat as plain text */
    }
  }
  return { text: raw, images: [] };
}

interface RawToolCall {
  id?: string;
  function?: { name?: string; arguments?: string };
}

/** Parses the tool calls stored on an assistant message: a list, or a JSON string of one. */
export function parseToolCalls(raw: unknown): Array<{ id: string; name: string; args: string }> {
  if (isAbsent(raw)) return [];
  let calls: unknown = raw;
  if (typeof raw === 'string') {
    try {
      calls = JSON.parse(raw);
    } catch {
      return [];
    }
  }
  if (!Array.isArray(calls)) return [];
  return calls
    .filter((c): c is RawToolCall => typeof c === 'object' && c !== null)
    .map((c) => ({
      id: c.id ?? '',
      name: c.function?.name ?? 'tool',
      args: c.function?.arguments ?? '',
    }));
}

/** Sub-agent messages belong to an activity feed, not the main transcript. */
export function isMainTranscript(message: StoredMessage): boolean {
  return isAbsent(message.parent_type) || message.parent_type === 'main';
}

/**
 * The block `chat_completions` appends to a user message that has file attachments, so the model
 * sees them (backend/chat/router.py builds it, backend/chat/message_edit.py re-appends it on edit;
 * keep the three in step). It starts with this prefix and ends the text with `]`; the files are
 * listed between as `- <name> (ID: <file_id>)` lines.
 */
const ATTACHMENT_NOTE_PREFIX = '\n\n[System Note: The user has attached the following files';
// Lazy name, so a file name may contain newlines; an entry ends before the next `\n- ` or the `]`.
const ATTACHMENT_NOTE_ENTRY = /\n- ([\s\S]+?) \(ID: ([^)]+)\)(?=\n- |\]$)/g;

/**
 * Splits the router's attachment note off a user message for display. Returns the text before the
 * note and the files the note lists (size and type are not in the note, so they default like
 * `parseAttachments`). The stored message is untouched, so the model still gets the note. Text that
 * does not end in the router's note, including text that merely mentions "System Note", is returned
 * as is.
 */
export function splitAttachmentNote(text: string): { text: string; noteFiles: UploadedFile[] } {
  const start = text.lastIndexOf(ATTACHMENT_NOTE_PREFIX);
  if (start < 0 || !text.endsWith(']')) return { text, noteFiles: [] };
  const noteFiles: UploadedFile[] = [];
  for (const [, name = '', fileId = ''] of text.slice(start).matchAll(ATTACHMENT_NOTE_ENTRY)) {
    noteFiles.push({ file_id: fileId, name, size: 0, mime_type: '' });
  }
  return { text: text.slice(0, start), noteFiles };
}

/** Reads the stored attachment list of a user message; malformed entries are skipped. */
export function parseAttachments(raw: unknown): UploadedFile[] {
  if (!Array.isArray(raw)) return [];
  const files: UploadedFile[] = [];
  for (const item of raw) {
    if (typeof item !== 'object' || item === null) continue;
    const f = item as Record<string, unknown>;
    if (typeof f.file_id !== 'string' || typeof f.name !== 'string') continue;
    files.push({
      file_id: f.file_id,
      name: f.name,
      size: typeof f.size === 'number' ? f.size : 0,
      mime_type: typeof f.mime_type === 'string' ? f.mime_type : '',
    });
  }
  return files;
}

type Row = Pick<StoredSubAgentRow, 'content' | 'reasoning_content' | 'tool_calls'>;

/** Reasoning, text, then tool steps of one stored assistant row, in the order the stream sends them. */
function assistantSteps(row: Row, agent: string | null, results: Map<string, string>): Step[] {
  const { thoughts, cleaned } = parseContent(clean(row.content));
  const reasoning = [clean(row.reasoning_content), thoughts].filter(Boolean).join('\n');
  const steps: Step[] = [];
  if (reasoning) steps.push({ kind: 'reasoning', text: reasoning, agent });
  if (cleaned) steps.push({ kind: 'text', text: cleaned, agent });
  for (const call of parseToolCalls(row.tool_calls)) {
    steps.push({ kind: 'tool', ...call, result: results.get(call.id) ?? null, agent });
  }
  return steps;
}

/** The row's sub-agent steps, placed after the main-agent tool step that started them. */
function withSubAgentSteps(
  own: Step[],
  sub: StoredSubAgentRow[],
  results: Map<string, string>,
): Step[] {
  if (sub.length === 0) return own;
  let lastTool = -1;
  own.forEach((step, i) => {
    if (step.kind === 'tool') lastTool = i;
  });
  const after = new Map<number, Step[]>();
  const ordered = [...sub].sort((a, b) => (a.sequence_order ?? 0) - (b.sequence_order ?? 0));
  for (const row of ordered) {
    const agent = isAbsent(row.agent_name) ? 'sub_agent' : String(row.agent_name);
    let steps: Step[];
    if (row.role === 'event') {
      const text = clean(row.content);
      steps = text ? [{ kind: 'event', text, agent }] : [];
    } else if (row.role === 'assistant') {
      steps = assistantSteps(row, agent, results);
    } else {
      steps = [];
    }
    if (steps.length === 0) continue;
    const parent = String(row.parent_message_id ?? '');
    let anchor = own.findIndex((s) => s.kind === 'tool' && s.id === parent);
    if (anchor === -1) anchor = lastTool !== -1 ? lastTool : own.length - 1;
    after.set(anchor, [...(after.get(anchor) ?? []), ...steps]);
  }
  const out: Step[] = [];
  own.forEach((step, i) => {
    out.push(step, ...(after.get(i) ?? []));
  });
  // No main steps at all: the sub-agent steps stand alone.
  return own.length === 0 ? [...(after.get(-1) ?? [])] : out;
}

export function toTurns(messages: StoredMessage[]): Turn[] {
  const results = new Map<string, string>();
  for (const m of messages) {
    if (m.role === 'tool' && !isAbsent(m.tool_call_id)) {
      results.set(String(m.tool_call_id), clean(m.content));
    }
    for (const sub of m.sub_agent_history ?? []) {
      if (sub.role === 'tool' && !isAbsent(sub.tool_call_id)) {
        results.set(String(sub.tool_call_id), clean(sub.content));
      }
    }
  }

  const turns: Turn[] = [];
  /** The assistant turn being built: everything after a user row up to the next one. */
  let current: Extract<Turn, { kind: 'assistant' }> | null = null;
  const open = (id: string): Extract<Turn, { kind: 'assistant' }> => {
    if (!current) {
      current = { kind: 'assistant', id, messageIds: [id], steps: [], model: null };
      turns.push(current);
    }
    return current;
  };

  for (const m of messages) {
    if (!isMainTranscript(m)) continue;
    const id = String(m.id);
    if (m.role === 'user') {
      current = null;
      const { text: rawText, images } = parseUserContent(clean(m.content));
      // The note is for the model: show its files as chips, keep it out of the text and edit box.
      const { text, noteFiles } = splitAttachmentNote(rawText);
      const stored = parseAttachments(m.attachments);
      turns.push({
        kind: 'user',
        id,
        text,
        images,
        files: stored.length > 0 ? stored : noteFiles,
        time: m.timestamp ?? null,
      });
    } else if (m.role === 'assistant') {
      const turn = open(id);
      if (!turn.messageIds.includes(id)) turn.messageIds.push(id);
      if (!isAbsent(m.model)) turn.model = String(m.model);
      if (!isAbsent(m.timestamp)) turn.time = m.timestamp;
      const own = assistantSteps(m, null, results);
      turn.steps.push(...withSubAgentSteps(own, m.sub_agent_history ?? [], results));
    } else if (m.role === 'event') {
      const text = clean(m.content);
      if (text) open(id).steps.push({ kind: 'event', text, agent: null });
    } else if (m.role === 'tool' && !isAbsent(m.tool_call_id)) {
      const turn = open(id);
      const known = turn.steps.some((s) => s.kind === 'tool' && s.id === String(m.tool_call_id));
      if (!known) {
        turn.steps.push({
          kind: 'tool',
          id: String(m.tool_call_id),
          name: isAbsent(m.name) ? 'tool' : String(m.name),
          args: '',
          result: clean(m.content),
          agent: null,
        });
      }
    }
  }
  return turns;
}
