import type { ReactNode } from 'react';
import { Icon } from '../icons/Icon';
import { cx } from '../../lib/cx';

export interface ChipProps {
  children: ReactNode;
  /** Blue tint: something that is switched on. */
  tint?: boolean;
  /** Shows a remove button with this spoken name. */
  removeLabel?: string;
  onRemove?: () => void;
}

/** A chip: a chosen thing shown in a row (a tool that is on, an attached file). */
export function Chip({ children, tint = false, removeLabel, onRemove }: ChipProps) {
  return (
    <span className={cx('ui-chip', tint && 'ui-chip--tint')}>
      {children}
      {onRemove ? (
        <button
          type="button"
          className="ui-chip__remove"
          aria-label={removeLabel}
          onClick={onRemove}
        >
          <Icon name="close" size={12} />
        </button>
      ) : null}
    </span>
  );
}
