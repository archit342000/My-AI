import { useEffect, useId, useRef, type ReactNode, type RefObject } from 'react';
import { createPortal } from 'react-dom';
import { IconButton } from './Button';
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
  /** Shows a back chevron in the header (sub-dialogs return to their parent). */
  onBack?: () => void;
  /** Element to focus on open instead of the first focusable control. */
  initialFocusRef?: RefObject<HTMLElement | null>;
}

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select, textarea, [tabindex]:not([tabindex="-1"])';

/**
 * Dialog with Escape-to-close (top of stack only), backdrop click, focus trap, focus restore and
 * body scroll lock. Matches the legacy `.modal-backdrop.open` / `.modal-content` markup.
 */
export function Modal({
  open,
  onClose,
  title,
  children,
  footer,
  maxWidth = 560,
  id,
  onBack,
  initialFocusRef,
}: ModalProps) {
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
    // Focus the requested control, else the first focusable one, or the dialog itself.
    const first = dialogRef.current?.querySelector<HTMLElement>(FOCUSABLE);
    (initialFocusRef?.current ?? first ?? dialogRef.current)?.focus();
    return () => {
      release();
      unlockScroll();
      previouslyFocused?.focus?.();
    };
  }, [open, initialFocusRef]);

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

  // Portalled to <body>: sidebar/message ancestors use backdrop-filter, which would trap `position: fixed`.
  return createPortal(
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
        style={{ maxWidth }} // dynamic-style
        onKeyDown={onKeyDown}
      >
        <div className="modal-header">
          <div className="ui-modal__header-row">
            {onBack ? (
              <IconButton icon="chevron-left" label="Back" tooltip={false} onClick={onBack} />
            ) : null}
            <h2 id={titleId} className="font-heading ui-modal__title">
              {title}
            </h2>
            <IconButton icon="close" label="Close" tooltip={false} onClick={onClose} />
          </div>
        </div>
        <div className="modal-body">{children}</div>
        {footer ? <div className="modal-footer">{footer}</div> : null}
      </div>
    </div>,
    document.body,
  );
}
