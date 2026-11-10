import { useState, type ReactNode } from 'react';
import { cx } from '../../lib/cx';
import { useThoughtStore } from '../../state/thought-store';
import type { TimelineItem } from '../../lib/thought-timeline';
import { TimelineEntry } from './TimelineEntry';
import { ThoughtFullView } from './ThoughtFullView';

const BRAIN = (
  <svg
    width="16"
    height="16"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2.5"
    aria-hidden="true"
  >
    <path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 4.3-3.6z" />
    <path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-4.3-3.6z" />
  </svg>
);

const CHEVRON = (
  <svg
    className="thought-chevron"
    width="24"
    height="24"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    aria-hidden="true"
  >
    <path d="M6 9l6 6 6-6" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const EXPAND = (
  <svg
    width="16"
    height="16"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2.5"
    aria-hidden="true"
  >
    <path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

/**
 * The thought box of one assistant turn, as the legacy row: a header row (avatar beside the box
 * header) and, under it at full width, the timeline of the turn's steps. While the turn streams the
 * header says "Thinking..." with the latest activity; it says "Thought Process" once the stream ended.
 * Whether the box is open lives in the thought store under `turnKey`, so it survives the swap from the
 * live row to the saved one.
 */
export function ThoughtBox({
  turnKey,
  items,
  active,
  status,
  avatar,
}: {
  turnKey: string;
  items: TimelineItem[];
  active: boolean;
  status: string | null;
  avatar: ReactNode;
}) {
  const expanded = useThoughtStore((s) => Boolean(s.expanded[turnKey]));
  const toggle = useThoughtStore((s) => s.toggle);
  const [fullView, setFullView] = useState(false);
  return (
    <>
      <div className="assistant-header-row">
        <div className="assistant-avatar-column">{avatar}</div>
        <div className="thought-section-wrapper">
          <div className="thought-content-wrapper">
            <div
              className={cx(
                'thought-container',
                active && 'reasoning-active',
                expanded && 'expanded',
              )}
            >
              <div className="thought-header">
                <button
                  type="button"
                  className="thought-toggle"
                  aria-expanded={expanded}
                  onClick={() => toggle(turnKey)}
                >
                  <span className="thought-status">
                    {BRAIN}
                    <span className="thought-header-title">
                      {active ? (
                        <>
                          Thinking...
                          <span className="thought-progress-dots" aria-hidden="true">
                            <span />
                            <span />
                            <span />
                          </span>
                        </>
                      ) : (
                        'Thought Process'
                      )}
                    </span>
                    {active && status ? (
                      <span className="thought-status-line">{status}</span>
                    ) : null}
                  </span>
                  {CHEVRON}
                </button>
                <div className="thought-actions">
                  <button
                    type="button"
                    className="thought-full-view-btn btn-ghost"
                    title="Full screen view"
                    aria-label="Full screen view"
                    disabled={items.length === 0}
                    onClick={() => setFullView(true)}
                  >
                    {EXPAND}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      <div className={cx('thought-timeline-wrapper full-width-reasoning', expanded && 'expanded')}>
        <div className="thought-body">
          <div className="thought-body-inner">
            {expanded ? (
              <div className="activity-feed-wrapper">
                <div className="activity-feed">
                  {items.map((item) => (
                    <TimelineEntry key={item.key} item={item} />
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        </div>
      </div>
      <ThoughtFullView open={fullView} onClose={() => setFullView(false)} items={items} />
    </>
  );
}
