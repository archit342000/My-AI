import {
  useEffect,
  useRef,
  useState,
  type KeyboardEvent,
  type ReactNode,
  type RefObject,
} from 'react';
import { Icon, type IconName } from '../icons/Icon';
import { cx } from '../../lib/cx';
import { Popover } from './Popover';

export type MenuEntry =
  | {
      type?: 'item';
      id: string;
      label: string;
      icon?: IconName;
      danger?: boolean;
      disabled?: boolean;
      /** Why the item is off, shown beside it. */
      reason?: string;
      /** Marks the item as the current choice (a tick-style highlight). */
      checked?: boolean;
      /** Keys that do the same, shown at the end (for example ['Ctrl', 'K']). */
      keys?: string[];
      onSelect: () => void;
    }
  | { type: 'separator'; id: string }
  | { type: 'group'; id: string; label: string }
  | {
      type: 'submenu';
      id: string;
      label: string;
      icon?: IconName;
      items: MenuEntry[];
      /** Adds a filter field above the items (use when there are many). */
      searchable?: boolean;
    };

export interface MenuTriggerProps {
  ref: RefObject<HTMLButtonElement | null>;
  onClick: () => void;
  'aria-haspopup': 'menu';
  'aria-expanded': boolean;
}

export interface MenuProps {
  items: MenuEntry[];
  /** Renders the trigger; spread the given props onto a button. Omit in controlled (`point`) mode. */
  trigger?: (props: MenuTriggerProps) => ReactNode;
  label?: string;
  width?: number;
  minWidth?: number;
  /**
   * Controlled context-menu mode: open at this viewport point while it is non-null, with no trigger.
   * `onClose` is called whenever the menu wants to close.
   */
  point?: { x: number; y: number } | null;
  onClose?: () => void;
}

/**
 * Action menu: ARIA menu pattern. Arrow keys move, Home/End jump, Right opens a submenu, Left or
 * Escape goes back, Enter/Space choose, Tab closes. Focus returns to the trigger on close.
 */
export function Menu({ items, trigger, label, width, minWidth = 200, point, onClose }: MenuProps) {
  const anchorRef = useRef<HTMLButtonElement>(null);
  const [internalOpen, setInternalOpen] = useState(false);
  const controlled = point !== undefined;
  const open = controlled ? point !== null : internalOpen;

  function close(reason?: 'escape' | 'outside') {
    if (controlled) {
      onClose?.();
      return;
    }
    setInternalOpen(false);
    if (reason !== 'outside') anchorRef.current?.focus();
  }

  return (
    <>
      {trigger
        ? trigger({
            ref: anchorRef,
            onClick: () => setInternalOpen((value) => !value),
            'aria-haspopup': 'menu',
            'aria-expanded': open,
          })
        : null}
      <Popover
        open={open}
        anchorRef={anchorRef}
        point={controlled && point ? point : undefined}
        onClose={close}
        role="menu"
        label={label}
        width={width}
        minWidth={minWidth}
      >
        <MenuList items={items} autoFocus onDone={() => close()} />
      </Popover>
    </>
  );
}

interface MenuListProps {
  items: MenuEntry[];
  autoFocus?: boolean;
  searchable?: boolean;
  /** Closes the whole menu (after an item is chosen). */
  onDone: () => void;
  /** Closes only this level (submenus). */
  onBack?: () => void;
}

type ActionItem = Extract<MenuEntry, { onSelect: () => void }>;

function isActionItem(entry: MenuEntry): entry is ActionItem {
  return entry.type === undefined || entry.type === 'item';
}

function enabledItems(list: HTMLElement): HTMLButtonElement[] {
  return Array.from(
    list.querySelectorAll<HTMLButtonElement>(
      ':scope > :is([role="menuitem"], [role="menuitemradio"]):not(:disabled)',
    ),
  );
}

export function MenuList({
  items,
  autoFocus = false,
  searchable = false,
  onDone,
  onBack,
}: MenuListProps) {
  const listRef = useRef<HTMLDivElement>(null);
  const [query, setQuery] = useState('');

  useEffect(() => {
    if (!autoFocus || searchable) return;
    const list = listRef.current;
    if (list) enabledItems(list)[0]?.focus();
  }, [autoFocus, searchable]);

  const q = query.trim().toLowerCase();
  const visible =
    searchable && q
      ? items.filter(
          (entry) =>
            entry.type !== 'separator' &&
            entry.type !== 'group' &&
            entry.label.toLowerCase().includes(q),
        )
      : items;

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const list = listRef.current;
    if (!list) return;
    const buttons = enabledItems(list);
    const index = buttons.indexOf(document.activeElement as HTMLButtonElement);
    if (event.key === 'Tab') {
      onDone();
    } else if (event.key === 'ArrowLeft' && onBack) {
      event.preventDefault();
      onBack();
    } else if (event.key === 'ArrowDown') {
      event.preventDefault();
      buttons[(index + 1) % buttons.length]?.focus();
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      buttons[(index - 1 + buttons.length) % buttons.length]?.focus();
    } else if (event.key === 'Home') {
      event.preventDefault();
      buttons[0]?.focus();
    } else if (event.key === 'End') {
      event.preventDefault();
      buttons[buttons.length - 1]?.focus();
    }
  }

  return (
    <div ref={listRef} className="ui-menu" role="none" onKeyDown={onKeyDown}>
      {searchable ? (
        <input
          className="ui-input ui-menu__search"
          type="search"
          placeholder="Filter"
          aria-label="Filter"
          value={query}
          autoFocus
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'ArrowDown') {
              event.preventDefault();
              const list = listRef.current;
              if (list) enabledItems(list)[0]?.focus();
            } else if (event.key === 'Enter') {
              event.preventDefault();
              const first = visible.find(isActionItem);
              if (first && !first.disabled) {
                onDone();
                first.onSelect();
              }
            }
          }}
        />
      ) : null}
      {visible.map((entry) => {
        if (entry.type === 'separator') {
          return <div key={entry.id} role="separator" className="ui-menu__separator" />;
        }
        if (entry.type === 'group') {
          return (
            <div key={entry.id} role="presentation" className="ui-menu__group">
              {entry.label}
            </div>
          );
        }
        if (entry.type === 'submenu') {
          return <SubMenu key={entry.id} entry={entry} onDone={onDone} />;
        }
        return (
          <button
            key={entry.id}
            type="button"
            role={entry.checked === undefined ? 'menuitem' : 'menuitemradio'}
            aria-checked={entry.checked}
            tabIndex={-1}
            disabled={entry.disabled}
            className={cx('ui-menu__item', entry.danger && 'ui-menu__item--danger')}
            onClick={() => {
              onDone();
              entry.onSelect();
            }}
          >
            {entry.icon ? <Icon name={entry.icon} size={16} /> : null}
            <span className="ui-menu__label">{entry.label}</span>
            {entry.disabled && entry.reason ? (
              <span className="ui-menu__reason">{entry.reason}</span>
            ) : null}
            {entry.keys ? (
              <span className="ui-kbd-group" aria-hidden="true">
                {entry.keys.map((key) => (
                  <kbd key={key} className="ui-kbd">
                    {key}
                  </kbd>
                ))}
              </span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}

function SubMenu({
  entry,
  onDone,
}: {
  entry: Extract<MenuEntry, { type: 'submenu' }>;
  onDone: () => void;
}) {
  const ref = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false);

  function closeSub() {
    setOpen(false);
    ref.current?.focus();
  }

  return (
    <>
      <button
        ref={ref}
        type="button"
        role="menuitem"
        tabIndex={-1}
        aria-haspopup="menu"
        aria-expanded={open}
        data-open={open ? 'true' : 'false'}
        className="ui-menu__item"
        onMouseEnter={() => setOpen(true)}
        onClick={() => setOpen(true)}
        onKeyDown={(event) => {
          if (event.key === 'ArrowRight') {
            event.preventDefault();
            setOpen(true);
          }
        }}
      >
        {entry.icon ? <Icon name={entry.icon} size={16} /> : null}
        <span className="ui-menu__label">{entry.label}</span>
        <Icon name="chevron-right" size={14} className="ui-menu__chevron" />
      </button>
      <Popover
        open={open}
        anchorRef={ref}
        onClose={(reason) => {
          if (reason === 'outside') setOpen(false);
          else closeSub();
        }}
        placement="right"
        role="menu"
        label={entry.label}
        minWidth={220}
      >
        <MenuList
          items={entry.items}
          autoFocus
          searchable={entry.searchable}
          onDone={onDone}
          onBack={closeSub}
        />
      </Popover>
    </>
  );
}
