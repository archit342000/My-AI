import { useEffect, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { useBackLayer } from '../../hooks/useBackLayer';
import { lockScroll, unlockScroll } from '../../lib/scroll-lock';
import { showToast } from './toast-store';

export interface HoldScreenProps {
  open: boolean;
  /** What is happening, for example "Switching models". */
  title: string;
  /** One line of detail under it. */
  children?: ReactNode;
}

/**
 * The whole-screen wait (rule book 7.12): for the rare job during which nothing else can be used,
 * such as switching models. It says what is happening and cannot be dismissed.
 */
export function HoldScreen({ open, title, children }: HoldScreenProps) {
  useEffect(() => {
    if (!open) return undefined;
    lockScroll();
    return unlockScroll;
  }, [open]);
  // Back cannot skip the wait: it stays, and says so.
  useBackLayer(open, () => showToast('Still working. This one cannot be skipped.', 'info'), true);

  if (!open) return null;

  return createPortal(
    <div
      className="ui-hold"
      role="alertdialog"
      aria-modal="true"
      aria-label={title}
      aria-busy="true"
    >
      <div className="ui-hold__in">
        <h2 className="ui-hold__title">{title}</h2>
        {children ? <p className="ui-hold__text">{children}</p> : null}
        <div className="ui-hold__bar" aria-hidden="true">
          <i />
        </div>
      </div>
    </div>,
    document.body,
  );
}
