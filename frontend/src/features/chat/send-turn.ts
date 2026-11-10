/**
 * Runs one chat turn: optimistic user row, streamed assistant reply, then a refetch of the
 * persisted chat. Plain functions (no React) so the flow can be reasoned about and tested.
 */
import type { QueryClient } from '@tanstack/react-query';
import { chatsApi, queryKeys } from '../../api/chats';
import { ApiError } from '../../api/client';
import {
  buildCompletionBody,
  reattachStream,
  resumeStream,
  streamCompletion,
  type HistoryMessage,
  type UploadedFile,
} from '../../api/completions';
import { toTurns, turnText } from '../../lib/chat-model';
import { showToast } from '../../components/ui/toast-store';
import { useSettingsStore } from '../../state/settings-store';
import { useStreamStore, type PendingUser } from '../../state/stream-store';
import { useUiStore } from '../../state/ui-store';
import { applyChunk, emptyLiveTurn, StreamError, type StreamChunk } from './stream-reducer';

/** Same id shape as the legacy `generateId()`. */
export function generateChatId(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2);
}

export function historyFromCache(queryClient: QueryClient, chatId: string): HistoryMessage[] {
  const detail = queryClient.getQueryData<{ messages: Parameters<typeof toTurns>[0] }>(
    queryKeys.chat(chatId),
  );
  if (!detail) return [];
  // The server builds the model's context from its own stored messages and reads only the last
  // posted message, so this history (with the attachment note stripped for display) is not sent on.
  return toTurns(detail.messages).flatMap<HistoryMessage>((t) => {
    if (t.kind === 'user') return [{ role: 'user', content: t.text }];
    const text = turnText(t.steps);
    return text ? [{ role: 'assistant', content: text }] : [];
  });
}

/**
 * The error text of the server's 400 refusal of a send or resume while a turn runs or starts.
 * This exact string is part of the API contract in docs/standards/api.md (backend/chat/router.py
 * returns it from both routes); change them together.
 */
const TURN_IN_PROGRESS = 'a response is already in progress';

async function consume(
  queryClient: QueryClient,
  chatId: string,
  source: AsyncGenerator<unknown>,
  /** A 400 means the server refused the request before storing or starting anything (a send). */
  refusalIsToastOnly = false,
): Promise<void> {
  const store = useStreamStore.getState();
  let live = emptyLiveTurn();
  let listRefreshed = false;
  try {
    for await (const raw of source) {
      if (!listRefreshed) {
        // The first chunk means the server accepted the send and stored the user message, so a new
        // chat now has content and belongs in the sidebar before the reply finishes.
        listRefreshed = true;
        void queryClient.invalidateQueries({ queryKey: queryKeys.chats });
      }
      live = applyChunk(live, raw as StreamChunk);
      store.update(live);
    }
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      // The user pressed Stop: keep what arrived, marked as stopped (F-15).
      store.interrupt({ chatId, live, kind: 'stopped', message: null });
    } else if (
      err instanceof ApiError &&
      ((err.status === 400 && (refusalIsToastOnly || err.message === TURN_IN_PROGRESS)) ||
        // 429: over the per-user turn limit; the server refused it before storing or starting anything.
        err.status === 429)
    ) {
      // A send refused before anything was stored or started, or any request refused because a
      // turn is already in progress or the user is over their turn limit (also a Retry/resume):
      // toast only, no partial reply to keep.
      showToast(err.message, 'error');
    } else {
      const message = err instanceof Error ? err.message : 'Stream failed';
      // Keep the partial reply under an inline error with Retry (F-14).
      store.interrupt({ chatId, live, kind: 'error', message });
      if (!(err instanceof StreamError)) console.error(err);
      showToast(message, 'error');
    }
  } finally {
    await queryClient.invalidateQueries({ queryKey: queryKeys.chat(chatId) });
    // End the turn as soon as the saved chat is in: the live and pending rows then give way to the
    // saved ones in one render, with no moment where both are drawn.
    useStreamStore.getState().finish();
    await queryClient.invalidateQueries({ queryKey: queryKeys.chats });
  }
}

type Settings = ReturnType<typeof useSettingsStore.getState>;

/** The request body shared by a new turn (`/v1/chat/completions`) and Retry (`/resume`). */
function completionBody(
  settings: Settings,
  model: string,
  chatId: string,
  messages: HistoryMessage[],
  opts: { userPreferences: boolean; files?: UploadedFile[] },
): Record<string, unknown> {
  return buildCompletionBody({
    model,
    modelName: settings.modelName ?? model,
    messages,
    chatId,
    sampling: settings.sampling,
    modes: {
      researchMode: settings.modes.researchMode,
      userPreferences: opts.userPreferences,
      visionEnabled: settings.visionEnabled,
      fileSystemMode: settings.modes.fileSystemMode,
      browsingMode: settings.modes.browsingMode,
      gitMode: settings.modes.gitMode,
      codeExecutionMode: settings.modes.codeExecutionMode,
    },
    personaId: settings.personaId,
    folder: null,
    uploadedFiles: opts.files,
  });
}

export interface SendArgs {
  queryClient: QueryClient;
  chatId: string;
  text: string;
  files: UploadedFile[];
  /** Persist a brand-new chat first (title from the first message). */
  isNewChat: boolean;
  /** Temporary chat: user preferences are off and nothing is persisted client-side. */
  temporary?: boolean;
  /** Overrides the history taken from the cache (used by retry and regenerate). */
  history?: HistoryMessage[];
  /**
   * The user turn already exists in the transcript (retry, or regenerate after an edit), so no
   * optimistic "pending" user row is shown; otherwise the message would appear twice (F-16).
   */
  userTurnExists?: boolean;
}

export async function sendTurn({
  queryClient,
  chatId,
  text,
  files,
  isNewChat,
  temporary,
  history: historyOverride,
  userTurnExists = false,
}: SendArgs): Promise<void> {
  const settings = useSettingsStore.getState();
  if (!settings.model) {
    showToast('Select a model first', 'error');
    return;
  }
  if (useStreamStore.getState().chatId) return; // already streaming

  if (!historyOverride && !isNewChat && !queryClient.getQueryData(queryKeys.chat(chatId))) {
    // The chat is not in the cache, so its prior context is unknown; refuse rather than send without it.
    showToast('Could not load this chat. Reload the page and try again.', 'error');
    return;
  }
  const controller = new AbortController();
  const history = historyOverride ?? historyFromCache(queryClient, chatId);
  const pending: PendingUser | null = userTurnExists
    ? null
    : {
        text,
        images: [],
        files,
        ordinal: history.filter((m) => m.role === 'user').length + 1,
      };
  const messages: HistoryMessage[] = [
    ...history,
    { role: 'user', content: text, uploadedFiles: files.length ? files : undefined },
  ];

  useStreamStore.getState().start(chatId, pending, controller);

  if (isNewChat) {
    // A chat started from a workspace page is filed into that workspace on creation (F-47).
    const workspaceId = useUiStore.getState().newChatWorkspaceId;
    try {
      await chatsApi.patch(chatId, {
        title: text.substring(0, 50) || 'New Conversation',
        ...(workspaceId ? { workspace_id: workspaceId } : {}),
        user_preferences: settings.userPreferences,
        research_mode: settings.modes.researchMode ? 1 : 0,
        file_system_mode: settings.modes.fileSystemMode ? 1 : 0,
        browsing_mode: settings.modes.browsingMode ? 1 : 0,
        git_mode: settings.modes.gitMode ? 1 : 0,
        code_execution_mode: settings.modes.codeExecutionMode ? 1 : 0,
        thinking_profile: settings.sampling.thinking_profile,
      });
    } catch (err) {
      useStreamStore.getState().finish();
      showToast(err instanceof Error ? err.message : 'Could not create chat', 'error');
      return;
    }
    useUiStore.getState().setNewChatWorkspaceId(null);
  }

  const body = completionBody(settings, settings.model, chatId, messages, { userPreferences: temporary ? false : settings.userPreferences, files });

  await consume(queryClient, chatId, streamCompletion(body, controller.signal), true);
}

/**
 * Retry: regenerates the reply to the last stored user message through `/resume`. The server
 * reuses that message as stored (images and file note included), so no user row is added.
 */
export async function resumeTurn(queryClient: QueryClient, chatId: string): Promise<void> {
  const settings = useSettingsStore.getState();
  if (!settings.model) {
    showToast('Select a model first', 'error');
    return;
  }
  if (useStreamStore.getState().chatId) return; // already streaming

  const controller = new AbortController();
  useStreamStore.getState().start(chatId, null, controller);
  const body = completionBody(settings, settings.model, chatId, [], { userPreferences: settings.userPreferences });
  await consume(queryClient, chatId, resumeStream(chatId, body, controller.signal));
}

/** Stops the in-flight turn on the client and asks the server to stop generating. */
export async function stopTurn(): Promise<void> {
  const { chatId, controller } = useStreamStore.getState();
  controller?.abort();
  if (chatId) {
    try {
      await chatsApi.stop(chatId);
    } catch {
      /* the stream is already aborted; the server will finish on its own */
    }
  }
}

/** Reconnects to a turn that the server is still generating (after reload or navigation). */
export async function reattachTurn(queryClient: QueryClient, chatId: string): Promise<void> {
  if (useStreamStore.getState().chatId) return;
  const controller = new AbortController();
  useStreamStore.getState().start(chatId, null, controller);
  try {
    const source = await reattachStream(chatId, controller.signal);
    if (!source) {
      useStreamStore.getState().finish();
      await queryClient.invalidateQueries({ queryKey: queryKeys.chat(chatId) });
      return;
    }
    await consume(queryClient, chatId, source);
  } catch (err) {
    useStreamStore.getState().finish();
    console.error('Reattach failed', err);
  }
}
