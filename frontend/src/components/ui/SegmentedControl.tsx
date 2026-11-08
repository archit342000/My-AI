import { useRef } from 'react';
import { Icon, type IconName } from '../icons/Icon';
import { rovingTarget } from '../../lib/roving';

export interface SegmentedOption {
  value: string;
  label: string;
  icon?: IconName;
  disabled?: boolean;
}

export interface SegmentedControlProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: SegmentedOption[];
}

/** Compact single-choice control (radio group). Arrow keys select and move focus. */
export function SegmentedControl({ label, value, onChange, options }: SegmentedControlProps) {
  const refs = useRef<Array<HTMLButtonElement | null>>([]);
  const checkedIndex = options.findIndex((option) => option.value === value);

  function select(index: number) {
    const option = options[index];
    if (!option || option.disabled) return;
    onChange(option.value);
    refs.current[index]?.focus();
  }

  return (
    <div role="radiogroup" aria-label={label} className="ui-segmented">
      {options.map((option, index) => {
        const checked = option.value === value;
        return (
          <button
            key={option.value}
            ref={(el) => {
              refs.current[index] = el;
            }}
            type="button"
            role="radio"
            aria-checked={checked}
            tabIndex={checked || (checkedIndex < 0 && index === 0) ? 0 : -1}
            disabled={option.disabled}
            className="ui-segmented__item"
            onClick={() => select(index)}
            onKeyDown={(event) => {
              const next = rovingTarget(event.key, index, options.length);
              if (next === null) return;
              event.preventDefault();
              select(next);
            }}
          >
            {option.icon ? <Icon name={option.icon} size={14} /> : null}
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
