import { useId, useRef, useState, type KeyboardEvent } from 'react';
import { Icon } from '../icons/Icon';
import { cx } from '../../lib/cx';
import { groupOptions, type NumberedOption } from '../../lib/option-groups';
import { Popover } from './Popover';

type GroupedOption = NumberedOption<SelectOption>;

export interface SelectOption {
  value: string;
  label: string;
  /** Options with the same group are listed under one heading, in first-seen order. */
  group?: string;
  hint?: string;
  disabled?: boolean;
  /** Optional status dot before the label (e.g. a loaded model). */
  dot?: 'success' | 'warning' | 'off';
}

export interface SelectProps {
  id?: string;
  value: string;
  onChange: (value: string) => void;
  options: SelectOption[];
  placeholder?: string;
  'aria-label'?: string;
  disabled?: boolean;
  /** Adds a filter field at the top of the list. */
  searchable?: boolean;
  searchPlaceholder?: string;
  emptyText?: string;
  className?: string;
}

const DOT_CLASS: Record<NonNullable<SelectOption['dot']>, string> = {
  success: 'ui-dot ui-dot--success',
  warning: 'ui-dot ui-dot--warning',
  off: 'ui-dot',
};

/**
 * Custom listbox (ARIA combobox pattern). The trigger keeps focus and points aria-activedescendant
 * at the active option. ArrowUp/Down move, Home/End jump, type-ahead matches labels, Enter or Space
 * choose, Escape closes and returns focus. With `searchable`, focus moves into the filter field.
 */
export function Select({
  id,
  value,
  onChange,
  options,
  placeholder = 'Select…',
  'aria-label': ariaLabel,
  disabled = false,
  searchable = false,
  searchPlaceholder = 'Search',
  emptyText = 'No matches',
  className,
}: SelectProps) {
  const generatedId = useId();
  const baseId = id ?? generatedId;
  const listId = `${baseId}-listbox`;
  const triggerRef = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [active, setActive] = useState(-1);
  const typeahead = useRef({ text: '', at: 0 });

  const selected = options.find((option) => option.value === value);
  const q = query.trim().toLowerCase();
  const groups = groupOptions(
    q ? options.filter((option) => option.label.toLowerCase().includes(q)) : options,
  );
  const flat = groups.flatMap((group) => group.options);

  function openList() {
    const grouped = groupOptions(options).flatMap((group) => group.options);
    const current = grouped.find((option) => option.value === value);
    setQuery('');
    setActive(
      current && !current.disabled
        ? current.index
        : (grouped.find((option) => !option.disabled)?.index ?? -1),
    );
    setOpen(true);
  }

  function closeList() {
    setOpen(false);
    setQuery('');
    triggerRef.current?.focus();
  }

  function choose(option: GroupedOption) {
    if (option.disabled) return;
    onChange(option.value);
    closeList();
  }

  function move(delta: 1 | -1) {
    if (flat.length === 0) return;
    const start = flat.findIndex((option) => option.index === active);
    let position = start;
    for (let step = 0; step < flat.length; step++) {
      position = (position + delta + flat.length) % flat.length;
      if (!flat[position]!.disabled) {
        setActive(flat[position]!.index);
        return;
      }
    }
  }

  function typeAhead(key: string) {
    const now = Date.now();
    const buffer = typeahead.current;
    buffer.text = now - buffer.at > 500 ? key.toLowerCase() : buffer.text + key.toLowerCase();
    buffer.at = now;
    const start = Math.max(
      0,
      flat.findIndex((option) => option.index === active),
    );
    const ordered = [...flat.slice(start), ...flat.slice(0, start)];
    const hit = ordered.find(
      (option) => !option.disabled && option.label.toLowerCase().startsWith(buffer.text),
    );
    if (hit) setActive(hit.index);
  }

  function onKeyDown(event: KeyboardEvent<HTMLElement>) {
    if (!open) {
      if (['ArrowDown', 'ArrowUp', 'Enter', ' '].includes(event.key)) {
        event.preventDefault();
        openList();
      }
      return;
    }
    const enabled = flat.filter((option) => !option.disabled);
    switch (event.key) {
      case 'ArrowDown':
        event.preventDefault();
        move(1);
        return;
      case 'ArrowUp':
        event.preventDefault();
        move(-1);
        return;
      case 'Home':
        if (!searchable || event.currentTarget === triggerRef.current) {
          event.preventDefault();
          setActive(enabled[0]?.index ?? -1);
        }
        return;
      case 'End':
        if (!searchable || event.currentTarget === triggerRef.current) {
          event.preventDefault();
          setActive(enabled[enabled.length - 1]?.index ?? -1);
        }
        return;
      case 'Enter': {
        event.preventDefault();
        const chosen = flat.find((option) => option.index === active);
        if (chosen) choose(chosen);
        return;
      }
      case 'Tab':
        setOpen(false);
        return;
      default:
        if (
          !searchable &&
          event.key.length === 1 &&
          !event.ctrlKey &&
          !event.metaKey &&
          !event.altKey
        ) {
          typeAhead(event.key);
        }
    }
  }

  const activeOption = flat.find((option) => option.index === active);
  const activeId = open && activeOption ? `${baseId}-opt-${activeOption.index}` : undefined;

  return (
    <div className={cx('ui-select', className)}>
      <button
        ref={triggerRef}
        id={baseId}
        type="button"
        role="combobox"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? listId : undefined}
        aria-label={ariaLabel}
        aria-activedescendant={searchable ? undefined : activeId}
        disabled={disabled}
        className="ui-select__trigger"
        onClick={() => (open ? closeList() : openList())}
        onKeyDown={onKeyDown}
      >
        {selected?.dot ? <span className={DOT_CLASS[selected.dot]} aria-hidden="true" /> : null}
        <span className={cx('ui-select__value', !selected && 'ui-select__placeholder')}>
          {selected ? selected.label : placeholder}
        </span>
        <Icon name="chevron-down" size={16} className="ui-select__chevron" />
      </button>
      <Popover
        open={open}
        anchorRef={triggerRef}
        onClose={() => closeList()}
        role="listbox"
        sheetOnPhone
        id={listId}
        label={ariaLabel}
        minWidth={200}
      >
        {searchable ? (
          <input
            className="ui-input ui-select__search"
            type="search"
            autoFocus
            placeholder={searchPlaceholder}
            aria-label={searchPlaceholder}
            aria-controls={listId}
            aria-activedescendant={activeId}
            value={query}
            onChange={(event) => {
              const text = event.target.value;
              setQuery(text);
              const needle = text.trim().toLowerCase();
              const first = groupOptions(
                options.filter((option) => option.label.toLowerCase().includes(needle)),
              )
                .flatMap((group) => group.options)
                .find((option) => !option.disabled);
              setActive(first?.index ?? -1);
            }}
            onKeyDown={onKeyDown}
          />
        ) : null}
        <div className="ui-select__list">
          {groups.map((group) => (
            <div
              key={group.name ?? '__ungrouped'}
              role="group"
              aria-label={group.name ?? undefined}
            >
              {group.name ? (
                <div className="ui-select__group" aria-hidden="true">
                  {group.name}
                </div>
              ) : null}
              {group.options.map((option) => (
                <div
                  key={option.value}
                  id={`${baseId}-opt-${option.index}`}
                  role="option"
                  aria-selected={option.value === value}
                  aria-disabled={option.disabled ? true : undefined}
                  data-active={option.index === active ? 'true' : 'false'}
                  className="ui-select__option"
                  onMouseEnter={() => setActive(option.index)}
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => choose(option)}
                >
                  {option.dot ? (
                    <span className={DOT_CLASS[option.dot]} aria-hidden="true" />
                  ) : null}
                  <span className="ui-select__option-label">{option.label}</span>
                  {option.hint ? (
                    <span className="ui-select__option-hint">{option.hint}</span>
                  ) : null}
                </div>
              ))}
            </div>
          ))}
          {flat.length === 0 ? <div className="ui-select__empty">{emptyText}</div> : null}
        </div>
      </Popover>
    </div>
  );
}
