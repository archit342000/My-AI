import { useState } from 'react';
import type { ToolActivity as ToolActivityItem } from '../../lib/chat-model';
import { friendlyToolName } from './tool-names';
import { cx } from '../../lib/cx';

/** Results longer than this are clipped until the user asks for the rest. */
const CLIP_CHARS = 1500;

function prettyArgs(args: string): string {
  try {
    return JSON.stringify(JSON.parse(args), null, 2);
  } catch {
    return args;
  }
}

/** Text in a `<pre>`, clipped to CLIP_CHARS with a "Show more" toggle. */
function ClippedText({ text, label }: { text: string; label: string }) {
  const [full, setFull] = useState(false);
  const long = text.length > CLIP_CHARS;
  const shown = long && !full ? `${text.slice(0, CLIP_CHARS)}\n…` : text;
  return (
    <div className="activity-content" aria-label={label}>
      <pre className="font-mono">{shown}</pre>
      {long ? (
        <button type="button" className="activity-more" onClick={() => setFull((value) => !value)}>
          {full ? 'Show less' : `Show more (${Math.ceil(text.length / 1024)} KB)`}
        </button>
      ) : null}
    </div>
  );
}

/**
 * One tool call with its result, collapsed by default. The `expanded` class on `.activity-item`
 * drives the animated body (see components.css, "Tool activity").
 */
export function ToolActivityCard({ tool }: { tool: ToolActivityItem }) {
  const [open, setOpen] = useState(false);
  const label = friendlyToolName(tool.name);
  return (
    <div className={open ? 'activity-item expanded' : 'activity-item'}>
      <button type="button" className="activity-header" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
        <span className="activity-type">{label}</span>
        <span className="thought-chevron" aria-hidden="true">{open ? '▾' : '▸'}</span>
      </button>
      <div className="activity-content-wrapper">
        <div className="activity-body">
          <ClippedText text={prettyArgs(tool.args)} label="Arguments" />
          {tool.result !== null ? <ClippedText text={tool.result} label="Result" /> : null}
        </div>
      </div>
    </div>
  );
}

/** Compact list of the turn's tool calls, visible without expanding the thought block. */
export function ToolSummary({ tools }: { tools: ToolActivityItem[] }) {
  return (
    <ul className="tool-summary" aria-label="Tool calls">
      {tools.map((tool) => {
        const running = tool.result === null;
        return (
          <li
            key={tool.id || tool.name}
            className={cx('tool-summary__item', running && 'tool-summary__item--running')}
          >
            <span className="tool-summary__name">{friendlyToolName(tool.name)}</span>
            <span className="tool-summary__state">{running ? 'Running' : 'Done'}</span>
          </li>
        );
      })}
    </ul>
  );
}

export function ToolActivityFeed({ tools }: { tools: ToolActivityItem[] }) {
  if (tools.length === 0) return null;
  return (
    <div className="activity-feed-wrapper">
      <div className="activity-feed">
        {tools.map((tool) => (
          <ToolActivityCard key={tool.id || tool.name} tool={tool} />
        ))}
      </div>
    </div>
  );
}
