import type { ReactNode } from 'react';

/** A titled block of a settings dialog. */
export function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="settings-section">
      <h3 className="font-heading settings-section__title">{title}</h3>
      {children}
    </section>
  );
}

const TONE_CLASS = {
  info: 'settings-status--info',
  error: 'settings-status--error',
  success: 'settings-status--success',
} as const;

/** One-line result of a save or action; renders nothing without a message. */
export function Status({
  message,
  tone = 'info',
}: {
  message: string | null;
  tone?: 'info' | 'error' | 'success';
}) {
  if (!message) return null;
  return (
    <div role="status" className={`settings-status ${TONE_CLASS[tone]}`}>
      {message}
    </div>
  );
}
