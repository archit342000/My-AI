import type { ReactNode } from 'react';
import { Icon } from '../icons/Icon';

export interface CheckboxProps {
  checked: boolean | 'mixed';
  onChange: (checked: boolean) => void;
  /** The words beside the box. */
  children: ReactNode;
  disabled?: boolean;
}

/** Tick box (rule book 7.3): for a list where several things can be chosen. "mixed" means some of a group. */
export function Checkbox({ checked, onChange, children, disabled = false }: CheckboxProps) {
  return (
    <button
      type="button"
      role="checkbox"
      aria-checked={checked}
      disabled={disabled}
      className="ui-check"
      onClick={() => onChange(checked !== true)}
    >
      <span className="ui-check__box" aria-hidden="true">
        <Icon name={checked === 'mixed' ? 'minus' : 'check'} size={14} strokeWidth={3} />
      </span>
      <span>{children}</span>
    </button>
  );
}
