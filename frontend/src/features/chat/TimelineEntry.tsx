import { useState, type ReactNode } from 'react';
import { Markdown } from '../../components/markdown/Markdown';
import { toolDetail, toolFailed, type TimelineItem } from '../../lib/thought-timeline';
import { Icon } from '../../components/icons/Icon';
import { cx } from '../../lib/cx';
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
 * One entry of the thought process, as on the design's reference page: a thought is plain text on
 * the line; a tool call is a small box that folds open (light, name, what it was asked) to show
 * what was sent and what came back; a helper's steps are a box holding their own line of entries.
 * The `expanded` class on `.activity-item` shows the body (see styles/ds/chat.css).
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
  if (item.kind === 'reasoning' || item.kind === 'text') {
    return <Markdown text={item.text} className="timeline-reasoning" />;
  }

  let name: string;
  let detail = '';
  let light: ReactNode = null;
  let state: string | null = null;
  let body: ReactNode;
  const tone = item.kind === 'tool' ? 'tool-item' : 'sub-agent-item';
  if (item.kind === 'tool') {
    const running = item.result === null;
    const failed = toolFailed(item.result);
    name = friendlyToolName(item.name);
    detail = toolDetail(item.args);
    // The light is never the only sign: a call that is running or failed also says so in words.
    state = running ? 'Running' : failed ? 'Failed' : null;
    light = (
      <span className={cx('led', running ? 'busy' : failed ? 'bad' : 'ok')} aria-hidden="true" />
    );
    body = (
      <>
        <ClippedText text={prettyArgs(item.args)} label="Asked" />
        {item.result === null ? null : <ClippedText text={item.result} label="Answer" />}
      </>
    );
  } else {
    name = item.label;
    body = (
      <div className="activity-feed sub-agent-entries">
        {item.items.map((child) => (
          <TimelineEntry key={child.key} item={child} defaultOpen={defaultOpen} />
        ))}
      </div>
    );
  }
  return (
    <div className={cx('activity-item', tone, open && 'expanded')}>
      <button
        type="button"
        className="activity-header"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <Icon name="chevron-right" size={14} strokeWidth={2.4} className="activity-chevron" />
        {light}
        <span className="activity-type">{name}</span>
        <span className="activity-detail">{detail}</span>
        {state ? <span className="activity-running">{state}</span> : null}
      </button>
      <div className="activity-content-wrapper" inert={!open}>
        <div className="activity-body">{body}</div>
      </div>
    </div>
  );
}
