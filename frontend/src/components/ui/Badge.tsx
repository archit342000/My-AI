import type { ReactNode } from 'react';
import { cx } from '../../lib/cx';

export type BadgeTone = 'neutral' | 'success' | 'warning' | 'danger' | 'accent';

const TONE_CLASS: Record<BadgeTone, string> = {
  neutral: '',
  success: 'ui-badge--success',
  warning: 'ui-badge--warning',
  danger: 'ui-badge--danger',
  accent: 'ui-badge--accent',
};

export function Badge({ tone = 'neutral', children, className }: { tone?: BadgeTone; children: ReactNode; className?: string }) {
  return <span className={cx('ui-badge', TONE_CLASS[tone], className)}>{children}</span>;
}
