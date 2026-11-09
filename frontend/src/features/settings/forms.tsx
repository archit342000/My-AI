import type { ReactNode } from 'react';

/** Labelled form row used across the settings dialogs. */
export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 14 }}>
      <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--content-primary)' }}>{label}</span>
      {children}
      {hint ? <span style={{ fontSize: '0.75rem', color: 'var(--content-muted)' }}>{hint}</span> : null}
    </label>
  );
}

export function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section style={{ marginBottom: 20 }}>
      <h3 className="font-heading" style={{ fontSize: '0.95rem', margin: '0 0 10px', color: 'var(--content-secondary)' }}>{title}</h3>
      {children}
    </section>
  );
}

export function Toggle({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      className={`toggle-switch${checked ? ' active' : ''}`}
      onClick={() => onChange(!checked)}
    >
      <div className="toggle-handle" />
    </button>
  );
}

export function Status({ message, tone = 'info' }: { message: string | null; tone?: 'info' | 'error' | 'success' }) {
  if (!message) return null;
  const color = tone === 'error' ? 'var(--color-rose-500)' : tone === 'success' ? 'var(--color-emerald-500)' : 'var(--content-muted)';
  return <div role="status" style={{ fontSize: '0.8125rem', color, marginTop: 8 }}>{message}</div>;
}
