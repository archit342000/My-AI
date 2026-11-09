import { useEffect, useRef, useState, type ReactNode } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { chatsApi, queryKeys } from '../../api/chats';
import { Markdown } from '../../components/markdown/Markdown';
import { showToast } from '../../components/ui/toast-store';
import { useAutoFollow } from './useAutoFollow';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { Textarea } from '../../components/ui/Field';
import { EmptyState } from '../../components/ui/EmptyState';
import type { Turn } from '../../lib/chat-model';
import { emptyLiveTurn, type LiveTurn } from './stream-reducer';
import { useStreamStore, type InterruptedTurn, type PendingUser } from '../../state/stream-store';
import { ThoughtHeader, ThoughtTimeline } from './ThoughtBlock';
import { ToolActivityFeed, ToolSummary } from './ToolActivity';
import { MessageActions } from './MessageActions';
import { resumeTurn } from './send-turn';

const USER_AVATAR = (
  <div className="avatar-wrapper">
    <div className="avatar avatar--user">
      <svg
        width="20"
        height="20"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
        <circle cx="12" cy="7" r="4" />
      </svg>
    </div>
  </div>
);

const BOT_AVATAR = (
  <div className="avatar-wrapper">
    <div className="avatar-orbit" />
    <div className="avatar avatar--bot">
      <svg width="18" height="18" viewBox="0 0 32 32" fill="none">
        <path d="M16 2L26 12L16 30L6 12Z" fill="white" opacity="0.9" />
        <path d="M16 2L26 12H6Z" fill="white" opacity="0.3" />
        <circle cx="16" cy="12" r="2.5" fill="white" opacity="0.7" />
      </svg>
    </div>
  </div>
);

function UserTurn({
  turn,
  chatId,
  onChanged,
  canEdit,
  showRetry,
  onRetry,
}: {
  turn: Extract<Turn, { kind: 'user' }>;
  chatId: string;
  onChanged: () => void;
  canEdit: boolean;
  /** Last user turn with no reply after it: offers Retry under the bubble. */
  showRetry: boolean;
  onRetry: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(turn.text);
  const queryClient = useQueryClient();

  /**
   * Saves the edit. The server drops the old reply, so "regenerate" asks for a new one by resuming from
   * the edited stored message (no second user row; its images and attachment note are kept server-side).
   */
  async function save(regenerate: boolean) {
    // The server refuses empty content; an attachment-only message opens with an empty draft.
    if (!draft.trim()) return;
    try {
      await chatsApi.editMessage(chatId, turn.id, draft);
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Edit failed', 'error');
      return;
    }
    setEditing(false);
    onChanged();
    if (regenerate) await resumeTurn(queryClient, chatId);
  }

  function cancel() {
    setDraft(turn.text);
    setEditing(false);
  }

  return (
    <div className="message-row chat-row user-message" data-message-id={turn.id}>
      {USER_AVATAR}
      {editing ? (
        <div className="edit-box">
          <Textarea
            className="edit-textarea"
            autoGrow
            value={draft}
            rows={2}
            aria-label="Edit message"
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.nativeEvent.isComposing || e.keyCode === 229) return;
              if (e.key === 'Escape') {
                e.preventDefault();
                cancel();
              } else if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                void save(true);
              }
            }}
          />
          <div className="edit-box__actions">
            <Button variant="ghost" onClick={cancel}>
              Cancel
            </Button>
            <Button variant="secondary" disabled={!draft.trim()} onClick={() => void save(false)}>
              Save
            </Button>
            <Button variant="primary" disabled={!draft.trim()} onClick={() => void save(true)}>
              Save &amp; regenerate
            </Button>
          </div>
        </div>
      ) : (
        <div className="message-content raw-text-content">
          {turn.images.length > 0 ? (
            <div className="message-images">
              {turn.images.map((src, i) => (
                <img key={i} src={src} alt="" className="lightbox-img message-image" />
              ))}
            </div>
          ) : null}
          {turn.text ? <Markdown text={turn.text} className="message-text-wrapper" /> : null}
          {turn.files.length > 0 ? (
            <div className="message-attachments">
              {turn.files.map((f, i) => (
                <span key={`${i}:${f.file_id}`} className="message-file-chip">
                  {f.name}
                </span>
              ))}
            </div>
          ) : null}
          {showRetry ? (
            <Button variant="secondary" size="sm" className="turn-retry" onClick={onRetry}>
              Retry response
            </Button>
          ) : null}
        </div>
      )}
      {!editing ? (
        <MessageActions
          text={turn.text}
          role="user"
          canRetry={false}
          onEdit={canEdit ? () => setEditing(true) : undefined}
          onDelete={() => void remove(chatId, turn.id, queryClient, onChanged)}
        />
      ) : null}
    </div>
  );
}

async function remove(
  chatId: string,
  messageId: string,
  queryClient: ReturnType<typeof useQueryClient>,
  onChanged: () => void,
) {
  try {
    await chatsApi.deleteMessage(chatId, messageId);
    await queryClient.invalidateQueries({ queryKey: queryKeys.chat(chatId) });
    onChanged();
  } catch (err) {
    showToast(err instanceof Error ? err.message : 'Delete failed', 'error');
  }
}

/**
 * Shared bot-row body. The avatar is a grid column, so it lines up with the first block of the
 * turn whether or not a thought header exists (F-23).
 */
function BotBody({
  model,
  reasoning,
  tools,
  active,
  status,
  children,
  footer,
}: {
  model: string | null | undefined;
  reasoning: string;
  tools: Extract<Turn, { kind: 'assistant' }>['tools'];
  active: boolean;
  status?: string | null;
  children: ReactNode;
  footer?: ReactNode;
}) {
  const [expanded, setExpanded] = useState(false);
  const hasReasoning = Boolean(reasoning) || tools.length > 0;
  return (
    <div className="bot-turn">
      <div className="bot-turn__avatar">{BOT_AVATAR}</div>
      <div className="bot-turn__body">
        {hasReasoning || active ? (
          <ThoughtHeader
            expanded={expanded}
            active={active}
            status={status ?? null}
            onToggle={() => setExpanded((v) => !v)}
          />
        ) : null}
        {tools.length > 0 ? <ToolSummary tools={tools} /> : null}
        {hasReasoning ? (
          <ThoughtTimeline expanded={expanded} reasoning={reasoning}>
            <ToolActivityFeed tools={tools} />
          </ThoughtTimeline>
        ) : null}
        <div className="message-content-wrapper">
          {children}
          {model ? (
            <div className="bot-message-footer">
              <span className="bot-model-label">{model}</span>
            </div>
          ) : null}
          {footer}
        </div>
      </div>
    </div>
  );
}

function AssistantTurn({
  turn,
  chatId,
  isLast,
  onRetry,
  onDelete,
}: {
  turn: Extract<Turn, { kind: 'assistant' }>;
  chatId: string;
  isLast: boolean;
  onRetry: () => void;
  onDelete: () => void;
}) {
  const queryClient = useQueryClient();
  return (
    <div className="message-row chat-row bot-message bot" data-message-id={turn.id}>
      <BotBody model={turn.model} reasoning={turn.thinking ?? ''} tools={turn.tools} active={false}>
        <Markdown text={turn.text} className="message-content raw-text-content" />
      </BotBody>
      <MessageActions
        text={turn.text}
        role="assistant"
        canRetry={isLast}
        onRetry={onRetry}
        onDelete={() => void remove(chatId, turn.id, queryClient, onDelete)}
      />
    </div>
  );
}

function LiveAssistant({ live }: { live: LiveTurn }) {
  const thinking = !live.content;
  return (
    <div className="message-row chat-row bot-message bot streaming thinking" data-live="true">
      <BotBody
        model={live.model}
        reasoning={live.reasoning ?? ''}
        tools={live.tools}
        active={thinking}
        status={live.events.at(-1) ?? null}
      >
        {live.redactNotice ? (
          <div className="validation-fixing">
            <span className="processing-spinner" /> {live.redactNotice}
          </div>
        ) : null}
        {live.content ? (
          <Markdown text={live.content} className="message-content raw-text-content" />
        ) : null}
      </BotBody>
    </div>
  );
}

/** A reply that ended early: the partial text stays, with a Stopped marker or the error and Retry. */
function InterruptedAssistant({
  interrupted,
  onRetry,
}: {
  interrupted: InterruptedTurn;
  onRetry: () => void;
}) {
  const { live } = interrupted;
  return (
    <div className="message-row chat-row bot-message bot" data-interrupted={interrupted.kind}>
      <BotBody model={live.model} reasoning={live.reasoning} tools={live.tools} active={false}>
        {live.content ? (
          <Markdown text={live.content} className="message-content raw-text-content" />
        ) : null}
      </BotBody>
      {interrupted.kind === 'error' ? (
        <div className="chat-error" role="alert">
          <span className="chat-error__message">{interrupted.message ?? 'The reply failed.'}</span>
          <Button variant="secondary" size="sm" onClick={onRetry}>
            Retry
          </Button>
        </div>
      ) : (
        <div className="turn-notice" role="status">
          <Badge>Stopped</Badge>
          <Button variant="secondary" size="sm" onClick={onRetry}>
            Retry
          </Button>
        </div>
      )}
    </div>
  );
}

function LiveUser({ pending }: { pending: PendingUser }) {
  return (
    <div className="message-row chat-row user-message" data-pending="true">
      {USER_AVATAR}
      <div className="message-content raw-text-content">
        {pending.text ? <Markdown text={pending.text} className="message-text-wrapper" /> : null}
        {pending.files.length ? (
          <div className="message-attachments">
            {pending.files.map((f) => (
              <span key={f.file_id} className="message-file-chip">
                {f.name}
              </span>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}

/** Scrollable transcript: persisted turns, the optimistic user row and the live assistant turn. */
export function MessageList({
  turns,
  chatId,
  onChanged,
}: {
  turns: Turn[];
  chatId: string;
  onChanged: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const queryClient = useQueryClient();
  const live = useStreamStore((s) => (s.chatId === chatId ? s.live : null));
  const pending = useStreamStore((s) => (s.chatId === chatId ? s.pending : null));
  const streaming = useStreamStore((s) => s.chatId === chatId);
  const interrupted = useStreamStore((s) =>
    s.interrupted?.chatId === chatId ? s.interrupted : null,
  );
  const dismissInterrupted = useStreamStore((s) => s.dismissInterrupted);
  const lastUserIdx = findLast(turns, (t) => t.kind === 'user');
  const follow = useAutoFollow(ref, chatId, pending);

  // A partial reply belongs to the screen it was shown on: drop it when the chat is left.
  useEffect(() => {
    return () => {
      const current = useStreamStore.getState().interrupted;
      if (current?.chatId === chatId) dismissInterrupted();
    };
  }, [chatId, dismissInterrupted]);

  // Once the server has persisted a reply after the user turn, the persisted copy takes over.
  const replyPersisted = turns.at(-1)?.kind === 'assistant';
  const showInterrupted = interrupted !== null && !replyPersisted;
  const lastHasReply = lastUserIdx >= 0 && turns.slice(lastUserIdx + 1).some((t) => t.kind === 'assistant');
  const showUserRetry = !streaming && !showInterrupted && lastUserIdx >= 0 && !lastHasReply;

  /** Retry regenerates from the stored user message, so attachments are reused as sent. */
  function retryLast() {
    void resumeTurn(queryClient, chatId);
  }

  async function retry(assistantIdx: number) {
    if (!turns.slice(0, assistantIdx).some((t) => t.kind === 'user')) return;
    try {
      await chatsApi.deleteMessage(chatId, turns[assistantIdx]!.id);
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Retry failed', 'error');
      return;
    }
    await queryClient.invalidateQueries({ queryKey: queryKeys.chat(chatId) });
    await resumeTurn(queryClient, chatId);
  }

  return (
    <div id="messages" ref={ref} className="messages-list">
      {turns.map((turn, i) =>
        turn.kind === 'user' ? (
          <UserTurn
            key={turn.id}
            turn={turn}
            chatId={chatId}
            onChanged={onChanged}
            canEdit={!streaming}
            showRetry={showUserRetry && i === lastUserIdx}
            onRetry={retryLast}
          />
        ) : (
          <AssistantTurn
            key={turn.id}
            turn={turn}
            chatId={chatId}
            isLast={i > lastUserIdx}
            onRetry={() => void retry(i)}
            onDelete={onChanged}
          />
        ),
      )}
      {turns.length === 0 && !pending && !streaming ? (
        <EmptyState
          className="chat-empty"
          icon="sparkles"
          title={<span className="font-heading">Hello there</span>}
          description="How can I help you today?"
        />
      ) : null}
      {pending ? <LiveUser pending={pending} /> : null}
      {streaming ? <LiveAssistant live={live ?? emptyLiveTurn()} /> : null}
      {showInterrupted && interrupted ? (
        <InterruptedAssistant interrupted={interrupted} onRetry={retryLast} />
      ) : null}
      {streaming && !follow.pinned ? (
        <button type="button" className="chat-jump-latest" onClick={follow.jumpToLatest}>
          Jump to latest
        </button>
      ) : null}
    </div>
  );
}

function findLast<T>(items: T[], pred: (t: T) => boolean): number {
  for (let i = items.length - 1; i >= 0; i--) if (pred(items[i]!)) return i;
  return -1;
}
