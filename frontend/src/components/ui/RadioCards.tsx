import { useRef } from 'react';
import { rovingTarget } from '../../lib/roving';

export interface RadioCardOption {
  value: string;
  title: string;
  description?: string;
  disabled?: boolean;
}

export interface RadioCardsProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: RadioCardOption[];
}

/** Radio group drawn as cards. Arrow keys select and move focus; Home and End jump. */
export function RadioCards({ label, value, onChange, options }: RadioCardsProps) {
  const refs = useRef<Array<HTMLButtonElement | null>>([]);
  const checkedIndex = options.findIndex((option) => option.value === value);

  function select(index: number) {
    const option = options[index];
    if (!option || option.disabled) return;
    onChange(option.value);
    refs.current[index]?.focus();
  }

  return (
    <div role="radiogroup" aria-label={label} className="ui-radio-cards">
      {options.map((option, index) => {
        const checked = option.value === value;
        const focusable = checked || (checkedIndex < 0 && index === 0);
        return (
          <button
            key={option.value}
            ref={(el) => {
              refs.current[index] = el;
            }}
            type="button"
            role="radio"
            aria-checked={checked}
            tabIndex={focusable ? 0 : -1}
            disabled={option.disabled}
            className="ui-radio-card"
            onClick={() => select(index)}
            onKeyDown={(event) => {
              const next = rovingTarget(event.key, index, options.length);
              if (next === null) return;
              event.preventDefault();
              select(next);
            }}
          >
            <span className="ui-radio-card__title">{option.title}</span>
            {option.description ? (
              <span className="ui-radio-card__description">{option.description}</span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}
