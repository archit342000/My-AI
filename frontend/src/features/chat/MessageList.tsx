import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { chatsApi, queryKeys } from '../../api/chats';
import { Markdown } from '../../components/markdown/Markdown';
import { showToast } from '../../components/ui/toast-store';
import { useAutoFollow } from './useAutoFollow';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { Textarea } from '../../components/ui/Field';
import { EmptyState } from '../../components/ui/EmptyState';
import { firstMessageId, turnText, type Step, type Turn } from '../../lib/chat-model';
import { statusOf, timelineOf } from '../../lib/thought-timeline';
import { emptyLiveTurn, type LiveTurn } from './stream-reducer';
import { useStreamStore, type InterruptedTurn, type PendingUser } from '../../state/stream-store';
import { ThoughtBox } from './ThoughtBox';
import { friendlyToolName } from './tool-names';
import { useModelDisplayName } from './useModelDisplayName';
import { thoughtKey, useThoughtStore } from '../../state/thought-store';
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
  const caretPlaced = useRef(false);
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
            autoFocus
            onFocus={(e) => {
              // The caret goes to the end once, when the editor opens; tabbing back in keeps where it was.
              if (caretPlaced.current) return;
              caretPlaced.current = true;
              const end = e.currentTarget.value.length;
              e.currentTarget.setSelectionRange(end, end);
            }}
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
          onEdit={
            canEdit
              ? () => {
                  caretPlaced.current = false;
                  setEditing(true);
                }
              : undefined
          }
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
    // The turn numbers after this one shift, so the open boxes of the chat are forgotten.
    useThoughtStore.getState().clearChat(chatId);
    await queryClient.invalidateQueries({ queryKey: queryKeys.chat(chatId) });
    // A chat with no messages or files leaves the sidebar list.
    await queryClient.invalidateQueries({ queryKey: queryKeys.chats });
    onChanged();
  } catch (err) {
    showToast(err instanceof Error ? err.message : 'Delete failed', 'error');
  }
}

/**
 * Shared bot-row body, laid out as the legacy row. A turn with a thought box (steps to show, or a turn
 * that is still streaming) has a header row with the avatar beside the box, the timeline under it and
 * the answer under that, all at full width. A turn with nothing to show has no box: the avatar then
 * sits beside the answer (F-23). The model label appears only once the turn has text.
 */
function BotBody({
  model,
  steps,
  active,
  turnKey,
  children,
  footer,
}: {
  model: string | null | undefined;
  steps: Step[];
  /** True for as long as the turn streams. */
  active: boolean;
  turnKey: string;
  children: ReactNode;
  footer?: ReactNode;
}) {
  const items = useMemo(() => timelineOf(steps), [steps]);
  const displayName = useModelDisplayName();
  const hasBox = active || items.length > 0;
  const content = (
    <div className="message-content-wrapper">
      {children}
      {model && turnText(steps) ? (
        <div className="bot-message-footer">
          <span className="bot-model-label">{displayName(model)}</span>
        </div>
      ) : null}
      {footer}
    </div>
  );
  if (!hasBox) {
    return (
      <div className="bot-turn">
        <div className="bot-turn__avatar">{BOT_AVATAR}</div>
        <div className="bot-turn__body">{content}</div>
      </div>
    );
  }
  return (
    <>
      <ThoughtBox
        turnKey={turnKey}
        items={items}
        active={active}
        status={active ? statusOf(steps, friendlyToolName) : null}
        avatar={BOT_AVATAR}
      />
      {content}
    </>
  );
}

function AssistantTurn({
  turn,
  chatId,
  ordinal,
  isLast,
  onRetry,
  onDelete,
}: {
  turn: Extract<Turn, { kind: 'assistant' }>;
  chatId: string;
  /** Number of user turns up to the one this reply answers. */
  ordinal: number;
  isLast: boolean;
  onRetry: () => void;
  onDelete: () => void;
}) {
  const queryClient = useQueryClient();
  const text = turnText(turn.steps);
  return (
    <div className="message-row chat-row bot-message bot" data-message-id={turn.id}>
      <BotBody
        model={turn.model}
        steps={turn.steps}
        active={false}
        turnKey={thoughtKey(chatId, ordinal)}
        footer={
          <MessageActions
            text={text}
            role="assistant"
            canRetry={isLast}
            onRetry={onRetry}
            onDelete={() => void remove(chatId, firstMessageId(turn), queryClient, onDelete)}
          />
        }
      >
        <Markdown text={text} className="message-content raw-text-content" />
      </BotBody>
    </div>
  );
}

function LiveAssistant({ live, turnKey }: { live: LiveTurn; turnKey: string }) {
  const content = turnText(live.steps);
  return (
    <div className="message-row chat-row bot-message bot streaming thinking" data-live="true">
      <BotBody model={live.model} steps={live.steps} active turnKey={turnKey}>
        {live.redactNotice ? (
          <div className="validation-fixing" role="status">
            <span className="ui-spinner" aria-hidden="true" /> Fixing the reply…
          </div>
        ) : null}
        {content ? <Markdown text={content} className="message-content raw-text-content" /> : null}
      </BotBody>
    </div>
  );
}

/** A reply that ended early: the partial text stays, with a Stopped marker or the error and Retry. */
function InterruptedAssistant({
  interrupted,
  turnKey,
  onRetry,
}: {
  interrupted: InterruptedTurn;
  turnKey: string;
  onRetry: () => void;
}) {
  const { live } = interrupted;
  const content = turnText(live.steps);
  // The notice sits in the bubble column, under the answer, like the action row of a finished reply.
  const notice =
    interrupted.kind === 'error' ? (
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
    );
  return (
    <div className="message-row chat-row bot-message bot" data-interrupted={interrupted.kind}>
      <BotBody model={live.model} steps={live.steps} active={false} turnKey={turnKey} footer={notice}>
        {content ? <Markdown text={content} className="message-content raw-text-content" /> : null}
      </BotBody>
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
  // The reply to the Nth user turn is box N, live or saved.
  // The pending row knows its own number: the saved copy of the same message may already be in `turns`.
  const liveKey = thoughtKey(
    chatId,
    pending?.ordinal ?? turns.filter((t) => t.kind === 'user').length,
  );
  const follow = useAutoFollow(ref, chatId, pending);
  /**
   * While a retry, resume or reattach streams, the live row replays the whole turn, so the persisted
   * rows of that turn are not drawn next to it. A new send has a pending user row instead: the
   * persisted rows are all earlier turns and stay.
   */
  const hidden = (turn: Turn, i: number) =>
    turn.kind === 'assistant' && streaming && !pending && i > lastUserIdx;

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
      await chatsApi.deleteMessage(chatId, firstMessageId(turns[assistantIdx]!));
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
        hidden(turn, i) ? null : turn.kind === 'user' ? (
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
            ordinal={userTurnsUpTo(turns, i)}
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
      {streaming ? <LiveAssistant live={live ?? emptyLiveTurn()} turnKey={liveKey} /> : null}
      {showInterrupted && interrupted ? (
        <InterruptedAssistant interrupted={interrupted} turnKey={liveKey} onRetry={retryLast} />
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

/** How many user turns there are up to and including index `i`. */
function userTurnsUpTo(turns: Turn[], i: number): number {
  return turns.slice(0, i + 1).filter((t) => t.kind === 'user').length;
}
