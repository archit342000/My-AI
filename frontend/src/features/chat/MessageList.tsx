import { useEffect, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { chatsApi, queryKeys } from '../../api/chats';
import { Markdown } from '../../components/markdown/Markdown';
import { showToast } from '../../components/ui/toast-store';
import { createAutoScroller } from '../../lib/scroll';
import type { Turn } from '../../lib/chat-model';
import type { LiveTurn } from './stream-reducer';
import type { PendingUser } from '../../state/stream-store';
import { useStreamStore } from '../../state/stream-store';
import { ThoughtBlock } from './ThoughtBlock';
import { ToolActivityFeed } from './ToolActivity';
import { MessageActions } from './MessageActions';
import { historyFromCache, sendTurn } from './send-turn';

function UserTurn({ turn, chatId, onChanged, canEdit }: { turn: Extract<Turn, { kind: 'user' }>; chatId: string; onChanged: () => void; canEdit: boolean }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(turn.text);
  const queryClient = useQueryClient();

  async function save() {
    try {
      await chatsApi.editMessage(chatId, turn.id, draft);
      setEditing(false);
      onChanged();
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Edit failed', 'error');
    }
  }

  return (
    <div className="message-row chat-row user-message" data-message-id={turn.id}>
      <div className="message-content-wrapper">
        {turn.images.length > 0 ? (
          <div className="message-images">
            {turn.images.map((src, i) => (
              <img key={i} src={src} alt="" className="lightbox-img" />
            ))}
          </div>
        ) : null}
        {editing ? (
          <div className="edit-box">
            <textarea className="edit-textarea" value={draft} onChange={(e) => setDraft(e.target.value)} rows={3} aria-label="Edit message" />
            <div style={{ display: 'flex', gap: 8 }}>
              <button type="button" className="btn-primary" onClick={() => void save()}>Save</button>
              <button type="button" className="btn-secondary" onClick={() => setEditing(false)}>Cancel</button>
            </div>
          </div>
        ) : turn.text ? (
          <div className="message-text-wrapper"><Markdown text={turn.text} /></div>
        ) : null}
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
    </div>
  );
}

async function remove(chatId: string, messageId: string, queryClient: ReturnType<typeof useQueryClient>, onChanged: () => void) {
  try {
    await chatsApi.deleteMessage(chatId, messageId);
    await queryClient.invalidateQueries({ queryKey: queryKeys.chat(chatId) });
    onChanged();
  } catch (err) {
    showToast(err instanceof Error ? err.message : 'Delete failed', 'error');
  }
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
      <div className="message-content-wrapper">
        {turn.model ? <div className="bot-model-label">{turn.model}</div> : null}
        {turn.thinking ? <ThoughtBlock text={turn.thinking} /> : null}
        <ToolActivityFeed tools={turn.tools} />
        {turn.text ? <div className="message-text-wrapper"><Markdown text={turn.text} /></div> : null}
        <MessageActions text={turn.text} role="assistant" canRetry={isLast} onRetry={onRetry} onDelete={() => void remove(chatId, turn.id, queryClient, onDelete)} />
      </div>
    </div>
  );
}

function LiveAssistant({ live }: { live: LiveTurn }) {
  const tools = live.tools;
  return (
    <div className="message-row chat-row bot-message bot streaming" data-live="true">
      <div className="message-content-wrapper">
        {live.model ? <div className="bot-model-label">{live.model}</div> : null}
        {live.reasoning ? <ThoughtBlock text={live.reasoning} /> : null}
        <ToolActivityFeed tools={tools} />
        {live.redactNotice ? <div className="validation-fixing"><span className="processing-spinner" /> {live.redactNotice}</div> : null}
        {live.content ? <div className="message-text-wrapper"><Markdown text={live.content} /></div> : null}
        {!live.content && !live.reasoning && tools.length === 0 ? (
          <div className="thought-progress-dots" aria-label="Generating"><span /><span /><span /></div>
        ) : null}
      </div>
    </div>
  );
}

function LiveUser({ pending }: { pending: PendingUser }) {
  return (
    <div className="message-row chat-row user-message" data-pending="true">
      <div className="message-content-wrapper">
        {pending.text ? <div className="message-text-wrapper"><Markdown text={pending.text} /></div> : null}
        {pending.files.length ? (
          <div className="message-attachments">
            {pending.files.map((f) => <span key={f.file_id} className="file-attachment-pill">{f.name}</span>)}
          </div>
        ) : null}
      </div>
    </div>
  );
}

/** Scrollable transcript: persisted turns, the optimistic user row and the live assistant turn. */
export function MessageList({ turns, chatId, onChanged }: { turns: Turn[]; chatId: string; onChanged: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const scroller = useRef(createAutoScroller());
  const queryClient = useQueryClient();
  const live = useStreamStore((s) => (s.chatId === chatId ? s.live : null));
  const pending = useStreamStore((s) => (s.chatId === chatId ? s.pending : null));
  const streaming = useStreamStore((s) => s.chatId === chatId);
  const streamError = useStreamStore((s) => (s.chatId === chatId ? s.error : null));
  const lastUserIdx = findLast(turns, (t) => t.kind === 'user');

  useEffect(() => {
    if (ref.current) scroller.current(ref.current, { forced: true });
  }, [chatId]);

  useEffect(() => {
    if (ref.current) scroller.current(ref.current);
  }, [turns.length, live?.content, live?.reasoning]);

  async function retry(assistantIdx: number) {
    const userTurn = turns.slice(0, assistantIdx).reverse().find((t) => t.kind === 'user');
    if (!userTurn || userTurn.kind !== 'user') return;
    const history = historyFromCache(queryClient, chatId).slice(0, Math.max(0, indexOfUser(turns, userTurn.id)));
    try {
      await chatsApi.deleteMessage(chatId, turns[assistantIdx]!.id);
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Retry failed', 'error');
      return;
    }
    await queryClient.invalidateQueries({ queryKey: queryKeys.chat(chatId) });
    await sendTurn({ queryClient, chatId, text: userTurn.text, files: [], isNewChat: false, history });
  }

  return (
    <div id="messages" ref={ref} className="messages-list">
      {turns.map((turn, i) =>
        turn.kind === 'user' ? (
          <UserTurn key={turn.id} turn={turn} chatId={chatId} onChanged={onChanged} canEdit={!streaming} />
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
      {pending ? <LiveUser pending={pending} /> : null}
      {streaming && live ? <LiveAssistant live={live} /> : null}
      {streamError ? <div className="chat-error" role="alert">{streamError}</div> : null}
    </div>
  );
}

function findLast<T>(items: T[], pred: (t: T) => boolean): number {
  for (let i = items.length - 1; i >= 0; i--) if (pred(items[i]!)) return i;
  return -1;
}

function indexOfUser(turns: Turn[], id: string): number {
  return turns.filter((t) => t.kind === 'user').findIndex((t) => t.id === id);
}

