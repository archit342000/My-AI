import { useEffect, useId, useRef, type ReactNode } from 'react';
import { Icon } from '../icons/Icon';
import { pushModal } from '../../lib/modal-stack';
import { lockScroll, unlockScroll } from '../../lib/scroll-lock';

export interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  children: ReactNode;
  /** Optional footer (buttons). */
  footer?: ReactNode;
  maxWidth?: number | string;
  id?: string;
}

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select, textarea, [tabindex]:not([tabindex="-1"])';

/**
 * Dialog with Escape-to-close (top of stack only), backdrop click, focus trap, focus restore and
 * body scroll lock. Matches the legacy `.modal-backdrop.open` / `.modal-content` markup.
 */
export function Modal({ open, onClose, title, children, footer, maxWidth = 560, id }: ModalProps) {
  const titleId = useId();
  const dialogRef = useRef<HTMLDivElement>(null);
  const onCloseRef = useRef(onClose);

  useEffect(() => {
    onCloseRef.current = onClose;
  });

  useEffect(() => {
    if (!open) return;
    const previouslyFocused = document.activeElement as HTMLElement | null;
    const release = pushModal(() => onCloseRef.current());
    lockScroll();
    // Focus the first focusable control, or the dialog itself.
    const first = dialogRef.current?.querySelector<HTMLElement>(FOCUSABLE);
    (first ?? dialogRef.current)?.focus();
    return () => {
      release();
      unlockScroll();
      previouslyFocused?.focus?.();
    };
  }, [open]);

  if (!open) return null;

  function onKeyDown(event: React.KeyboardEvent<HTMLDivElement>) {
    if (event.key !== 'Tab') return;
    const nodes = Array.from(dialogRef.current?.querySelectorAll<HTMLElement>(FOCUSABLE) ?? []);
    if (nodes.length === 0) return;
    const first = nodes[0]!;
    const last = nodes[nodes.length - 1]!;
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  return (
    <div
      className="modal-backdrop open"
      id={id}
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={dialogRef}
        className="modal-content"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        style={{ maxWidth }}
        onKeyDown={onKeyDown}
      >
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <h2
              id={titleId}
              className="font-heading"
              style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--content-primary)', margin: 0 }}
            >
              {title}
            </h2>
            <button
              type="button"
              className="btn-ghost"
              aria-label="Close"
              onClick={onClose}
              style={{ width: '2.5rem', height: '2.5rem', padding: 0, borderRadius: '0.75rem' }}
            >
              <Icon name="close" size={20} strokeWidth={2.5} />
            </button>
          </div>
        </div>
        <div className="modal-body">{children}</div>
        {footer ? <div className="modal-footer">{footer}</div> : null}
      </div>
    </div>
  );
}
