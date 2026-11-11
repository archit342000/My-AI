import type { CSSProperties } from 'react';
import { cx } from '../../lib/cx';

export interface SkeletonProps {
  /** Any CSS width ("70%", "12rem"). Full width when left out. */
  width?: string;
  /** Any CSS height. A line of text when left out. */
  height?: string;
  className?: string;
}

/**
 * One placeholder shape shown while something loads (rule book 7.12). A screen draws several in
 * the layout its real content will have, so nothing jumps when the content arrives.
 */
export function Skeleton({ width, height, className }: SkeletonProps) {
  const style = { '--skel-w': width, '--skel-h': height } as CSSProperties;
  return (
    <span
      className={cx('skel', className)}
      style={style} // dynamic-style
      aria-hidden="true"
    />
  );
}

/** Several placeholder lines of the given widths, announced once as "Loading". */
export function SkeletonLines({
  widths,
  label = 'Loading',
  className,
}: {
  widths: string[];
  label?: string;
  className?: string;
}) {
  return (
    <div className={cx('skel-lines', className)} role="status" aria-label={label}>
      {widths.map((width, i) => (
        <Skeleton key={i} width={width} />
      ))}
    </div>
  );
}
