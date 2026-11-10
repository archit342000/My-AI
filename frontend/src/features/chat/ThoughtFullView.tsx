import { Window } from '../../components/ui/Window';
import type { TimelineItem } from '../../lib/thought-timeline';
import { TimelineEntry } from './TimelineEntry';

/** The whole timeline of a turn in a dialog, every entry open. */
export function ThoughtFullView({
  open,
  onClose,
  items,
}: {
  open: boolean;
  onClose: () => void;
  items: TimelineItem[];
}) {
  return (
    <Window open={open} onClose={onClose} title="Thought process" maxWidth={820}>
      <div className="activity-feed thought-full-view">
        {items.map((item) => (
          <TimelineEntry key={item.key} item={item} defaultOpen />
        ))}
      </div>
    </Window>
  );
}
