import { cx } from '../../lib/cx';

export type StatusTone = 'neutral' | 'ok' | 'warn' | 'bad' | 'off';

const TONE_CLASS: Record<StatusTone, string | undefined> = {
  neutral: undefined,
  ok: 'ok',
  warn: 'warn',
  bad: 'bad',
  off: 'off',
};

export interface StatusLightProps {
  /** The word beside the light. Colour alone never carries the meaning. */
  label: string;
  tone?: StatusTone;
  /** The light pulses while something is in progress. */
  busy?: boolean;
  className?: string;
}

/** Status light with its word in a typewriter label (rule book 1.4): Ready, Thinking, Saved. */
export function StatusLight({
  label,
  tone = 'neutral',
  busy = false,
  className,
}: StatusLightProps) {
  return (
    <span className={cx('statline', className)} role="status">
      <span className={cx('led', TONE_CLASS[tone], busy && 'busy')} aria-hidden="true" />
      <span className="dat">{label}</span>
    </span>
  );
}
