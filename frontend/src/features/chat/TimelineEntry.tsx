import { useState, type ReactNode } from 'react';
import { Markdown } from '../../components/markdown/Markdown';
import type { TimelineItem } from '../../lib/thought-timeline';
import { Icon } from '../../components/icons/Icon';
import { ClippedText } from './ClippedText';
import { friendlyToolName } from './tool-names';

function prettyArgs(args: string): string {
  try {
    return JSON.stringify(JSON.parse(args), null, 2);
  } catch {
    // Arguments stream in as partial JSON, so a call that is still arriving is shown as received.
    return args;
  }
}

/**
 * One entry of the thought box: reasoning, a tool call, a tool result, a sub-agent's text or a
 * group of a sub-agent's entries, collapsed unless `defaultOpen`. The `expanded` class on
 * `.activity-item` drives the animated body (see components.css, "Tool activity").
 */
export function TimelineEntry({
  item,
  defaultOpen = false,
}: {
  item: TimelineItem;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  if (item.kind === 'event') {
    return (
      <div className="event-divider" role="separator" aria-label={item.text}>
        <span>{item.text}</span>
      </div>
    );
  }

  let type: string;
  let tone: string;
  let body: ReactNode;
  switch (item.kind) {
    case 'reasoning':
      type = 'Reasoning';
      tone = 'thinking-item';
      body = <Markdown text={item.text} className="timeline-reasoning" />;
      break;
    case 'text':
      type = 'Response';
      tone = 'thinking-item';
      body = <Markdown text={item.text} className="timeline-reasoning" />;
      break;
    case 'call':
      type = `Call: ${friendlyToolName(item.name)}`;
      tone = 'tool-call-item';
      body = <ClippedText text={prettyArgs(item.args)} label="Arguments" />;
      break;
    case 'result':
      type = `Result: ${friendlyToolName(item.name)}`;
      tone = 'tool-result-item';
      body = <ClippedText text={item.result} label="Result" />;
      break;
    case 'group':
      type = item.label;
      tone = 'sub-agent-item';
      body = (
        <div className="sub-agent-entries">
          {item.items.map((child) => (
            <TimelineEntry key={child.key} item={child} defaultOpen={defaultOpen} />
          ))}
        </div>
      );
      break;
  }
  const running = item.kind === 'call' && item.running;
  return (
    <div className={`activity-item ${tone}${open ? ' expanded' : ''}`}>
      <button
        type="button"
        className="activity-header"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <Icon name="chevron-right" size={12} strokeWidth={2.4} className="activity-chevron" />
        <span className="activity-type">{type}</span>
        {running ? <span className="activity-running">Running</span> : null}
      </button>
      <div className="activity-content-wrapper" inert={!open}>
        <div className="activity-body">{body}</div>
      </div>
    </div>
  );
}
