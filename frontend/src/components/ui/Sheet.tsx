import { useEffect, useRef, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { trapFocus } from '../../lib/focus-trap';
import { pushModal } from '../../lib/modal-stack';

export interface SheetProps {
  open: boolean;
  onClose: () => void;
  /** Spoken name of the sheet. */
  label: string;
  children: ReactNode;
  role?: 'dialog' | 'menu' | 'listbox';
  id?: string;
}

/**
 * The bottom sheet (rule book Part 6): what a menu, a drop-down or a small pop-up becomes on a
 * phone. Rises from the bottom over a veil; Escape, Back and a press on the veil close it.
 */
export function Sheet({ open, onClose, label, children, role = 'dialog', id }: SheetProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const onCloseRef = useRef(onClose);
  useEffect(() => {
    onCloseRef.current = onClose;
  });

  useEffect(() => {
    if (!open) return undefined;
    const previouslyFocused = document.activeElement as HTMLElement | null;
    const releaseModal = pushModal(() => onCloseRef.current());
    const releaseTrap = panelRef.current ? trapFocus(panelRef.current) : undefined;
    return () => {
      releaseModal();
      releaseTrap?.();
      previouslyFocused?.focus?.();
    };
  }, [open]);

  if (!open) return null;

  return createPortal(
    <div
      className="ui-sheet-veil"
      data-popover=""
      onPointerDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        ref={panelRef}
        id={id}
        role={role}
        aria-modal={role === 'dialog' ? true : undefined}
        aria-label={label}
        tabIndex={-1}
        className="ui-sheet"
      >
        <div className="ui-sheet__grip" aria-hidden="true" />
        {children}
      </div>
    </div>,
    document.body,
  );
}
