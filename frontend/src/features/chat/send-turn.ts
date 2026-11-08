/**
 * Runs one chat turn: optimistic user row, streamed assistant reply, then a refetch of the
 * persisted chat. Plain functions (no React) so the flow can be reasoned about and tested.
 */
import type { QueryClient } from '@tanstack/react-query';
import { chatsApi, queryKeys } from '../../api/chats';
import {
  buildCompletionBody,
  reattachStream,
  streamCompletion,
  type HistoryMessage,
  type UploadedFile,
} from '../../api/completions';
import { toTurns } from '../../lib/chat-model';
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
  return toTurns(detail.messages).flatMap<HistoryMessage>((t) =>
    t.kind === 'user'
      ? [{ role: 'user', content: t.text }]
      : t.text
        ? [{ role: 'assistant', content: t.text }]
        : [],
  );
}

async function consume(
  queryClient: QueryClient,
  chatId: string,
  source: AsyncGenerator<unknown>,
): Promise<void> {
  const store = useStreamStore.getState();
  let live = emptyLiveTurn();
  try {
    for await (const raw of source) {
      live = applyChunk(live, raw as StreamChunk);
      store.update(live);
    }
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      // The user pressed Stop: keep what arrived, marked as stopped (F-15).
      store.interrupt({ chatId, live, kind: 'stopped', message: null });
    } else {
      const message = err instanceof Error ? err.message : 'Stream failed';
      // Keep the partial reply under an inline error with Retry (F-14).
      store.interrupt({ chatId, live, kind: 'error', message });
      if (!(err instanceof StreamError)) console.error(err);
      showToast(message, 'error');
    }
  } finally {
    await queryClient.invalidateQueries({ queryKey: queryKeys.chat(chatId) });
    await queryClient.invalidateQueries({ queryKey: queryKeys.chats });
    useStreamStore.getState().finish();
  }
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

  const pending: PendingUser | null = userTurnExists
    ? null
    : {
        text,
        images: [],
        files,
      };
  if (!historyOverride && !isNewChat && !queryClient.getQueryData(queryKeys.chat(chatId))) {
    // The chat is not in the cache, so its prior context is unknown; refuse rather than send without it.
    showToast('Could not load this chat. Reload the page and try again.', 'error');
    return;
  }
  const controller = new AbortController();
  const history = historyOverride ?? historyFromCache(queryClient, chatId);
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

  const body = buildCompletionBody({
    model: settings.model,
    modelName: settings.modelName ?? settings.model,
    messages,
    chatId,
    sampling: settings.sampling,
    modes: {
      researchMode: settings.modes.researchMode,
      userPreferences: temporary ? false : settings.userPreferences,
      visionEnabled: settings.visionEnabled,
      fileSystemMode: settings.modes.fileSystemMode,
      browsingMode: settings.modes.browsingMode,
      gitMode: settings.modes.gitMode,
      codeExecutionMode: settings.modes.codeExecutionMode,
    },
    personaId: settings.personaId,
    folder: null,
    uploadedFiles: files,
  });

  await consume(queryClient, chatId, streamCompletion(body, controller.signal));
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
