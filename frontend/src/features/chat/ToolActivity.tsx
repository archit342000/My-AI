import { useState } from 'react';
import type { ToolActivity as ToolActivityItem } from '../../lib/chat-model';
import { TOOL_LABELS } from './tool-labels.generated';

function prettyArgs(args: string): string {
  try {
    return JSON.stringify(JSON.parse(args), null, 2);
  } catch {
    return args;
  }
}

/** One tool call with its result, collapsed by default (legacy `.activity-item`). */
export function ToolActivityCard({ tool }: { tool: ToolActivityItem }) {
  const [open, setOpen] = useState(false);
  const label = TOOL_LABELS[tool.name] ?? tool.name;
  return (
    <div className={`activity-item${open ? '' : ' collapsed'}`}>
      <button type="button" className="activity-header" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
        <span className="activity-type">{label}</span>
        <span className="thought-chevron" aria-hidden="true">{open ? '▾' : '▸'}</span>
      </button>
      {open ? (
        <div className="activity-content-wrapper">
          <div className="activity-content tool-call-content">
            <pre className="font-mono">{prettyArgs(tool.args)}</pre>
          </div>
          {tool.result !== null ? (
            <div className="activity-content tool-result-content">
              <pre className="font-mono">{tool.result}</pre>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
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
