import { cx } from '../../lib/cx';

/** The tick rule: the drawn divider under a header or between blocks. Decoration only. */
export function TickRule({ className }: { className?: string }) {
  return <div className={cx('ticks', className)} aria-hidden="true" />;
}
