import { useState } from 'react';
import { Icon } from '../../components/icons/Icon';
import { IconButton } from '../../components/ui/Button';
import { cx } from '../../lib/cx';
import { useThoughtStore } from '../../state/thought-store';
import { toolSummary, type TimelineItem } from '../../lib/thought-timeline';
import { TimelineEntry } from './TimelineEntry';
import { ThoughtFullView } from './ThoughtFullView';

/**
 * The Thought process box of one reply (rule book 1.2, "detail waits until asked"): one folded box
 * holding the reply's thoughts and tool calls in the order they happened. While the reply is being
 * written the header says "Thinking..." with the latest activity; afterwards "Thought process" and
 * how many tools were used. Whether the box is open lives in the thought store under `turnKey`, so
 * it survives the swap from the live row to the saved one.
 */
export function ThoughtBox({
  turnKey,
  items,
  active,
  status,
}: {
  turnKey: string;
  items: TimelineItem[];
  active: boolean;
  status: string | null;
}) {
  const expanded = useThoughtStore((s) => Boolean(s.expanded[turnKey]));
  const toggle = useThoughtStore((s) => s.toggle);
  const [fullView, setFullView] = useState(false);
  const detail = active ? status : toolSummary(items);
  return (
    <div className={cx('thought-container', active && 'reasoning-active', expanded && 'expanded')}>
      <div className="thought-header">
        <button
          type="button"
          className="thought-toggle"
          aria-expanded={expanded}
          onClick={() => toggle(turnKey)}
        >
          <Icon name="chevron-right" size={14} strokeWidth={2.2} className="thought-chevron" />
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
              'Thought process'
            )}
          </span>
          {detail ? <span className="thought-status-line">{detail}</span> : null}
        </button>
        <div className="thought-actions">
          <IconButton
            icon="expand"
            size="sm"
            className="thought-full-view-btn"
            label="Open bigger view"
            disabled={items.length === 0}
            onClick={() => setFullView(true)}
          />
        </div>
      </div>
      {expanded ? (
        <div className="thought-timeline-wrapper thought-body">
          <div className="activity-feed">
            {items.map((item) => (
              <TimelineEntry key={item.key} item={item} />
            ))}
          </div>
        </div>
      ) : null}
      <ThoughtFullView open={fullView} onClose={() => setFullView(false)} items={items} />
    </div>
  );
}
