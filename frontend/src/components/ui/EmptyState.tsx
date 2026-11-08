import type { ReactNode } from 'react';
import { Icon, type IconName } from '../icons/Icon';
import { cx } from '../../lib/cx';

export interface EmptyStateProps {
  icon?: IconName;
  title: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
  className?: string;
}

/** Placeholder for an empty list or screen: icon, title, optional text and one action. */
export function EmptyState({ icon = 'info', title, description, action, className }: EmptyStateProps) {
  return (
    <div className={cx('ui-empty', className)}>
      <Icon name={icon} size={28} className="ui-empty__icon" />
      <div className="ui-empty__title">{title}</div>
      {description ? <div className="ui-empty__description">{description}</div> : null}
      {action ? <div className="ui-empty__action">{action}</div> : null}
    </div>
  );
}
