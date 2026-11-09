/**
 * Request body and stream helpers for `/v1/chat/completions` (and the resume/reattach
 * endpoints). The body matches what the legacy `sendMessage` posts, field for field.
 */
import { apiRequest } from './client';
import { readSse } from './sse';

export interface SamplingParams {
  max_tokens: number;
  thinking_budget_tokens: number;
  enable_thinking: boolean;
  thinking_profile: string;
  temperature?: number;
  top_p?: number;
  top_k?: number;
  min_p?: number;
  presence_penalty?: number;
  frequency_penalty?: number;
}

export interface HistoryMessage {
  role: 'user' | 'assistant';
  content: string;
  uploadedFiles?: UploadedFile[];
}

export interface UploadedFile {
  file_id: string;
  name: string;
  size: number;
  mime_type: string;
}

export interface CompletionOptions {
  model: string;
  modelName: string;
  messages: HistoryMessage[];
  chatId: string;
  sampling: SamplingParams;
  modes: {
    researchMode: boolean;
    userPreferences: boolean;
    visionEnabled: boolean;
    fileSystemMode: boolean;
    browsingMode: boolean;
    gitMode: boolean;
    codeExecutionMode: boolean;
  };
  personaId: string | null;
  folder: string | null;
  uploadedFiles?: UploadedFile[];
}

export function buildCompletionBody(o: CompletionOptions): Record<string, unknown> {
  return {
    model: o.model,
    lastModelName: o.modelName,
    messages: o.messages,
    userPreferences: o.modes.userPreferences,
    researchMode: o.modes.researchMode,
    visionEnabled: o.modes.visionEnabled,
    fileSystemMode: o.modes.fileSystemMode,
    browsingMode: o.modes.browsingMode,
    gitMode: o.modes.gitMode,
    code_execution_mode: o.modes.codeExecutionMode,
    persona_id: o.personaId,
    chatId: o.chatId,
    folder: o.folder,
    stream: true,
    stream_options: { include_usage: true },
    uploadedFiles: o.uploadedFiles && o.uploadedFiles.length > 0 ? o.uploadedFiles : undefined,
    ...o.sampling,
  };
}

/** POSTs a completion and yields parsed stream chunks. Throws on HTTP errors (with the server message). */
export async function* streamCompletion(body: unknown, signal: AbortSignal): AsyncGenerator<unknown> {
  const response = await apiRequest('/v1/chat/completions', { method: 'POST', json: body, signal });
  if (!response.body) throw new Error('Empty response from server');
  yield* readSse(response.body);
}

/**
 * Regenerates the reply to the last stored user message (Retry). The server reads that message
 * itself, so no history or files are sent. Throws on HTTP errors (with the server message).
 */
export async function* resumeStream(chatId: string, body: unknown, signal: AbortSignal): AsyncGenerator<unknown> {
  const response = await apiRequest(`/api/chats/${encodeURIComponent(chatId)}/resume`, {
    method: 'POST',
    json: body,
    signal,
  });
  if (!response.body) throw new Error('Empty response from server');
  yield* readSse(response.body);
}

/** Reattaches to an in-flight turn. Resolves to `null` when the server reports it already finished (204). */
export async function reattachStream(chatId: string, signal: AbortSignal): Promise<AsyncGenerator<unknown> | null> {
  const response = await apiRequest(`/api/chats/${encodeURIComponent(chatId)}/stream`, { method: 'GET', signal });
  if (response.status === 204 || !response.body) return null;
  return readSse(response.body);
}
