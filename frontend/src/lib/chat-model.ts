/**
 * Converts stored messages into display turns. Pure, so it is unit-tested.
 * Tool results (role `tool`) are attached to the assistant tool call with the same id.
 */
import { parseContent } from './markdown/content';
import type { StoredMessage } from '../api/types';
import type { UploadedFile } from '../api/completions';

export interface ToolActivity {
  id: string;
  name: string;
  args: string;
  result: string | null;
}

export type Turn =
  | { kind: 'user'; id: string; text: string; images: string[]; files: UploadedFile[] }
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
      const { text: rawText, images } = parseUserContent(clean(m.content));
      // The note is for the model: show its files as chips, keep it out of the text and edit box.
      const { text, noteFiles } = splitAttachmentNote(rawText);
      const stored = parseAttachments(m.attachments);
      turns.push({ kind: 'user', id, text, images, files: stored.length > 0 ? stored : noteFiles });
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
