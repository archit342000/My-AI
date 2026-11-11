import type { ReactNode } from 'react';
import { cx } from '../../lib/cx';
import { DottedDrawing, type DrawingName } from './DottedDrawing';

export interface EmptyStateProps {
  /** The dotted drawing: nothing here yet (the default), nothing found, no connection, something broke, gone. */
  drawing?: DrawingName;
  title: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
  className?: string;
}

/**
 * An empty list or screen (rule book 7.12): a small dotted drawing, one line saying what is
 * missing, a line of help and at most one way forward.
 */
export function EmptyState({
  drawing = 'nothing',
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div className={cx('ui-empty', className)}>
      <DottedDrawing name={drawing} size={44} />
      <div className="ui-empty__title">{title}</div>
      {description ? <div className="ui-empty__description">{description}</div> : null}
      {action ? <div className="ui-empty__action">{action}</div> : null}
    </div>
  );
}
