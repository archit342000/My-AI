import { useEffect, useRef } from 'react';
import { Markdown } from '../../components/markdown/Markdown';
import { createAutoScroller } from '../../lib/scroll';
import type { Turn } from '../../lib/chat-model';
import { ThoughtBlock } from './ThoughtBlock';
import { ToolActivityFeed } from './ToolActivity';

function UserTurn({ turn }: { turn: Extract<Turn, { kind: 'user' }> }) {
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
        {turn.text ? <div className="message-text-wrapper"><Markdown text={turn.text} /></div> : null}
      </div>
    </div>
  );
}

function AssistantTurn({ turn }: { turn: Extract<Turn, { kind: 'assistant' }> }) {
  return (
    <div className="message-row chat-row bot-message bot" data-message-id={turn.id}>
      <div className="message-content-wrapper">
        {turn.model ? <div className="bot-model-label">{turn.model}</div> : null}
        {turn.thinking ? <ThoughtBlock text={turn.thinking} /> : null}
        <ToolActivityFeed tools={turn.tools} />
        {turn.text ? <div className="message-text-wrapper"><Markdown text={turn.text} /></div> : null}
      </div>
    </div>
  );
}

/** Scrollable transcript. Pins to the bottom on load and while the user is already near it. */
export function MessageList({ turns, chatId }: { turns: Turn[]; chatId: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const scroller = useRef(createAutoScroller());

  useEffect(() => {
    if (ref.current) scroller.current(ref.current, { forced: true });
  }, [chatId]);

  useEffect(() => {
    if (ref.current) scroller.current(ref.current);
  }, [turns.length]);

  return (
    <div id="messages" ref={ref} className="messages-list">
      {turns.map((turn) =>
        turn.kind === 'user' ? <UserTurn key={turn.id} turn={turn} /> : <AssistantTurn key={turn.id} turn={turn} />,
      )}
    </div>
  );
}
