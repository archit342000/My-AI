import { useState } from 'react';
import { Markdown } from '../../components/markdown/Markdown';

/** Collapsible reasoning block (legacy `.thought-container`). Collapsed by default. */
export function ThoughtBlock({ text }: { text: string }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className={`thought-container${expanded ? ' expanded' : ''}`}>
      <button type="button" className="thought-header" aria-expanded={expanded} onClick={() => setExpanded((v) => !v)}>
        <span className="thought-header-title">Thought process</span>
        <span className="thought-chevron" aria-hidden="true">{expanded ? '▾' : '▸'}</span>
      </button>
      {expanded ? (
        <div className="thought-body">
          <div className="thought-body-inner">
            <Markdown text={text} className="message-content raw-text-content thought-text" />
          </div>
        </div>
      ) : null}
    </div>
  );
}
