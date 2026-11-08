import type { ReactNode } from 'react';
import { Markdown } from '../../components/markdown/Markdown';

const BRAIN = (
  <svg
    width="16"
    height="16"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2.5"
  >
    <path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 4.3-3.6z" />
    <path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-4.3-3.6z" />
  </svg>
);

/** Thought chip under the avatar. While streaming it shows the latest event as a status line. */
export function ThoughtHeader({
  expanded,
  active,
  status = null,
  onToggle,
}: {
  expanded: boolean;
  active: boolean;
  status?: string | null;
  onToggle: () => void;
}) {
  return (
    <div className="thought-section-wrapper">
      <div className="thought-content-wrapper">
        <div
          className={`thought-container${active ? ' reasoning-active' : ''}${expanded ? ' expanded' : ''}`}
        >
          <div
            className="thought-header"
            role="button"
            tabIndex={0}
            aria-expanded={expanded}
            onClick={onToggle}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                onToggle();
              }
            }}
          >
            <div className="thought-status">
              {BRAIN}
              <span className="thought-header-title">
                {active ? (
                  <>
                    Thinking...
                    <span className="thought-progress-dots">
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
                <span className="thought-status-line" role="status">
                  {status}
                </span>
              ) : null}
            </div>
            <div className="thought-actions">
              <svg
                className="thought-chevron"
                width="24"
                height="24"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <path d="M6 9l6 6 6-6" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/** Expandable body under the header row (legacy `.thought-timeline-wrapper`). */
export function ThoughtTimeline({
  expanded,
  reasoning,
  children,
}: {
  expanded: boolean;
  reasoning: string;
  children?: ReactNode;
}) {
  return (
    <div className={`thought-timeline-wrapper full-width-reasoning${expanded ? ' expanded' : ''}`}>
      <div className="thought-body">
        <div className="thought-body-inner">
          {reasoning ? (
            <Markdown text={reasoning} className="message-content raw-text-content thought-text" />
          ) : null}
          {children}
        </div>
      </div>
    </div>
  );
}
