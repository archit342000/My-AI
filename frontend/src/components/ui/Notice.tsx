import type { ReactNode } from 'react';
import { cx } from '../../lib/cx';
import { Button, IconButton } from './Button';

export type NoticeTone = 'info' | 'ok' | 'warn' | 'bad';

const TONE_CLASS: Record<NoticeTone, string> = {
  info: 'ui-notice--info',
  ok: 'ui-notice--ok',
  warn: 'ui-notice--warn',
  bad: 'ui-notice--bad',
};

export interface NoticeProps {
  tone?: NoticeTone;
  children: ReactNode;
  /** One way forward, for example "Try again". */
  actionLabel?: string;
  onAction?: () => void;
  /** Shows a close button with this spoken name. */
  dismissLabel?: string;
  onDismiss?: () => void;
  className?: string;
}

/**
 * The notice strip (rule book 7.11): something the person should know about this screen, staying
 * until it is dealt with. Problems are announced at once; the rest politely.
 */
export function Notice({
  tone = 'info',
  children,
  actionLabel,
  onAction,
  dismissLabel,
  onDismiss,
  className,
}: NoticeProps) {
  return (
    <div
      role={tone === 'bad' ? 'alert' : 'status'}
      className={cx('ui-notice', TONE_CLASS[tone], className)}
    >
      <span className="ui-notice__light" aria-hidden="true" />
      <div className="ui-notice__text">{children}</div>
      {actionLabel && onAction ? (
        <Button variant="secondary" size="sm" onClick={onAction}>
          {actionLabel}
        </Button>
      ) : null}
      {onDismiss ? (
        <IconButton icon="close" size="sm" label={dismissLabel ?? 'Close'} onClick={onDismiss} />
      ) : null}
    </div>
  );
}
