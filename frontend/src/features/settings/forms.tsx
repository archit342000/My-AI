import { useId, type ReactNode } from 'react';
import { TickRule } from '../../components/ui/TickRule';

/** One of the seven parts of the settings page. `id` is what the section list scrolls to. */
export function SettingsSection({
  id,
  title,
  lead,
  children,
}: {
  id: string;
  title: string;
  /** One line under the title saying what this part is. */
  lead?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section
      id={`settings-${id}`}
      className="set-section"
      aria-labelledby={`settings-${id}-title`}
      data-section={id}
    >
      <h2 id={`settings-${id}-title`} className="set-section__title">
        {title}
      </h2>
      {lead ? <p className="ui-hint set-lead">{lead}</p> : null}
      {children}
    </section>
  );
}

/** A small heading inside a section: a typewriter label and the tick rule. */
export function SubHead({ children, danger = false }: { children: ReactNode; danger?: boolean }) {
  return (
    <div className="block-head set-sub">
      <h3 className={danger ? 'sec set-sub__danger' : 'sec'}>{children}</h3>
      <TickRule />
    </div>
  );
}

/**
 * One setting: its name and a line of help on the left, its control on the right (under it on a
 * phone when the control is wide). The control gets the ids to name itself with.
 */
export function SettingRow({
  label,
  hint,
  wide = false,
  children,
}: {
  label: ReactNode;
  hint?: ReactNode;
  /** The control needs room (a slider, a drop-down, a choice of three): it drops under the text on a phone. */
  wide?: boolean;
  children: (ids: { id: string; labelId: string; hintId: string | undefined }) => ReactNode;
}) {
  const id = useId();
  const labelId = `${id}-label`;
  const hintId = hint ? `${id}-hint` : undefined;
  return (
    <div className={wide ? 'set-row set-row--wide' : 'set-row'}>
      <div className="set-row__text">
        <label id={labelId} htmlFor={id} className="set-row__label">
          {label}
        </label>
        {hint ? (
          <div id={hintId} className="ui-hint">
            {hint}
          </div>
        ) : null}
      </div>
      <div className="set-row__control">{children({ id, labelId, hintId })}</div>
    </div>
  );
}

const TONE_CLASS = {
  info: 'settings-status--info',
  error: 'settings-status--error',
  success: 'settings-status--success',
} as const;

/** One-line result of an action; renders nothing without a message. */
export function Status({
  message,
  tone = 'info',
}: {
  message: string | null;
  tone?: 'info' | 'error' | 'success';
}) {
  if (!message) return null;
  return (
    <div
      role={tone === 'error' ? 'alert' : 'status'}
      className={`settings-status ${TONE_CLASS[tone]}`}
    >
      {message}
    </div>
  );
}
