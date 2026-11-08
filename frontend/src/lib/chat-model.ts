/**
 * Converts stored messages into display turns. Pure, so it is unit-tested.
 * Tool results (role `tool`) are attached to the assistant tool call with the same id.
 */
import { parseContent } from './markdown/content';
import type { StoredMessage } from '../api/types';

export interface ToolActivity {
  id: string;
  name: string;
  args: string;
  result: string | null;
}

export type Turn =
  | { kind: 'user'; id: string; text: string; images: string[] }
  | { kind: 'assistant'; id: string; text: string; thinking: string; model: string | null; tools: ToolActivity[] };

const ABSENT = new Set(['', 'None', 'null', 'undefined']);

/** True when a stored field carries no value. */
export function isAbsent(value: unknown): boolean {
  return value === null || value === undefined || (typeof value === 'string' && ABSENT.has(value.trim()));
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

/** Parses the JSON array of tool calls stored on an assistant message. */
export function parseToolCalls(raw: string | null | undefined): Array<{ id: string; name: string; args: string }> {
  if (isAbsent(raw)) return [];
  try {
    const calls = JSON.parse(raw as string) as RawToolCall[];
    if (!Array.isArray(calls)) return [];
    return calls.map((c) => ({
      id: c.id ?? '',
      name: c.function?.name ?? 'tool',
      args: c.function?.arguments ?? '',
    }));
  } catch {
    return [];
  }
}

/** Sub-agent messages belong to an activity feed, not the main transcript. */
export function isMainTranscript(message: StoredMessage): boolean {
  return isAbsent(message.parent_type) || message.parent_type === 'main';
}

export function toTurns(messages: StoredMessage[]): Turn[] {
  const results = new Map<string, string>();
  for (const m of messages) {
    if (m.role === 'tool' && !isAbsent(m.tool_call_id)) {
      results.set(String(m.tool_call_id), clean(m.content));
    }
  }

  const turns: Turn[] = [];
  for (const m of messages) {
    if (!isMainTranscript(m)) continue;
    const id = String(m.id);
    if (m.role === 'user') {
      const { text, images } = parseUserContent(clean(m.content));
      turns.push({ kind: 'user', id, text, images });
    } else if (m.role === 'assistant') {
      const rawContent = clean(m.content);
      const { thoughts, cleaned } = parseContent(rawContent);
      const reasoning = clean(m.reasoning_content);
      const thinking = [reasoning, thoughts].filter(Boolean).join('\n');
      const tools = parseToolCalls(m.tool_calls).map((call) => ({
        id: call.id,
        name: call.name,
        args: call.args,
        result: results.get(call.id) ?? null,
      }));
      turns.push({ kind: 'assistant', id, text: cleaned, thinking, model: isAbsent(m.model) ? null : String(m.model), tools });
    }
  }
  return turns;
}
