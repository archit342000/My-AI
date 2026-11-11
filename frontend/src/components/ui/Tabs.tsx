import { useRef } from 'react';
import { rovingTarget } from '../../lib/roving';

export interface TabOption {
  value: string;
  label: string;
  /** Id of the panel this tab shows, for `aria-controls`. */
  panelId?: string;
}

export interface TabsProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: TabOption[];
}

/** Tabs (rule book 7.4): switch what is shown below. Arrow keys move and select; Home and End jump. */
export function Tabs({ label, value, onChange, options }: TabsProps) {
  const refs = useRef<Array<HTMLButtonElement | null>>([]);

  function select(index: number) {
    const option = options[index];
    if (!option) return;
    onChange(option.value);
    refs.current[index]?.focus();
  }

  return (
    <div role="tablist" aria-label={label} className="ui-tabs">
      {options.map((option, index) => {
        const selected = option.value === value;
        return (
          <button
            key={option.value}
            ref={(el) => {
              refs.current[index] = el;
            }}
            type="button"
            role="tab"
            aria-selected={selected}
            aria-controls={option.panelId}
            tabIndex={selected ? 0 : -1}
            className="ui-tabs__tab"
            onClick={() => select(index)}
            onKeyDown={(event) => {
              const target = rovingTarget(event.key, index, options.length);
              if (target === null) return;
              event.preventDefault();
              select(target);
            }}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
