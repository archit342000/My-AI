import { useEffect, useRef, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { Icon, type IconName } from '../icons/Icon';

export interface MenuItem {
  id: string;
  label: string;
  icon?: IconName;
  danger?: boolean;
  disabled?: boolean;
  onSelect: () => void;
}

export interface ContextMenuProps {
  x: number;
  y: number;
  items: MenuItem[];
  onClose: () => void;
  /** Optional header node, e.g. the name of the item the menu is for. */
  header?: ReactNode;
}

/**
 * Fixed-position menu (legacy `.sidebar-context-menu.open`). Closes on Escape, outside pointer
 * down, scroll, and after any item is chosen.
 */
export function ContextMenu({ x, y, items, onClose, header }: ContextMenuProps) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onPointerDown(e: PointerEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
    }
    document.addEventListener('pointerdown', onPointerDown);
    document.addEventListener('keydown', onKey);
    window.addEventListener('scroll', onClose, true);
    window.addEventListener('resize', onClose);
    return () => {
      document.removeEventListener('pointerdown', onPointerDown);
      document.removeEventListener('keydown', onKey);
      window.removeEventListener('scroll', onClose, true);
      window.removeEventListener('resize', onClose);
    };
  }, [onClose]);

  const maxHeight = Math.max(160, window.innerHeight - 16);
  const top = Math.max(
    8,
    Math.min(y, window.innerHeight - Math.min(maxHeight, 56 + items.length * 40) - 8),
  );
  const left = Math.max(8, Math.min(x, window.innerWidth - 260));

  return createPortal(
    <div
      ref={ref}
      className="sidebar-context-menu open"
      role="menu"
      style={{ left, top, maxHeight, overflowY: 'auto' }}
    >
      {header ? <div className="sidebar-context-menu-header">{header}</div> : null}
      {items.map((item) => (
        <button
          key={item.id}
          type="button"
          role="menuitem"
          className={`sidebar-context-menu-item${item.danger ? ' danger' : ''}`}
          disabled={item.disabled}
          onClick={() => {
            onClose();
            item.onSelect();
          }}
        >
          {item.icon ? <Icon name={item.icon} size={16} /> : null}
          <span>{item.label}</span>
        </button>
      ))}
    </div>,
    document.body,
  );
}
