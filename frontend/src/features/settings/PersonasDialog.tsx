import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { personasApi, settingsKeys, type Persona } from '../../api/settings';
import { CrudDialog } from './CrudList';
import { Field, inputStyle, Toggle } from './forms';

type PersonaBody = Omit<Persona, 'id'>;

const EMPTY: PersonaBody = {
  name: '',
  content: '',
  is_default: 0,
  research_mode: 0,
  file_system_mode: 0,
  browsing_mode: 0,
  git_mode: 0,
};

export function PersonasDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const queryClient = useQueryClient();
  const list = useQuery({ queryKey: settingsKeys.personas, queryFn: personasApi.list, enabled: open });
  const refresh = () => queryClient.invalidateQueries({ queryKey: settingsKeys.personas });
  return (
    <CrudDialog<Persona>
      open={open}
      onClose={onClose}
      title="Personas"
      emptyText="No personas yet. A persona sets the assistant's role and instructions."
      items={list.data ?? []}
      describe={(p) => ({ id: p.id, title: p.name + (p.is_default ? ' (default)' : ''), subtitle: p.content.slice(0, 120) })}
      renderForm={(initial, onDone) => <PersonaForm initial={initial} onDone={onDone} onSaved={refresh} />}
      onDelete={async (item) => {
        await personasApi.remove(item.id);
        await refresh();
      }}
    />
  );
}

function PersonaForm({ initial, onDone, onSaved }: { initial: Persona | null; onDone: () => void; onSaved: () => Promise<unknown> }) {
  const [form, setForm] = useState<PersonaBody>(initial ? { ...EMPTY, ...initial } : EMPTY);
  const [error, setError] = useState<string | null>(null);
  const set = <K extends keyof PersonaBody>(key: K, value: PersonaBody[K]) => setForm((f) => ({ ...f, [key]: value }));
  const flag = (key: 'is_default' | 'research_mode' | 'file_system_mode' | 'browsing_mode' | 'git_mode', label: string) => (
    <Field label={label}>
      <Toggle checked={Boolean(form[key])} onChange={(v) => set(key, v ? 1 : 0)} label={label} />
    </Field>
  );
  return (
    <form
      onSubmit={async (e) => {
        e.preventDefault();
        if (!form.name.trim() || !form.content.trim()) {
          setError('Name and instructions are required.');
          return;
        }
        try {
          if (initial) await personasApi.update(initial.id, form);
          else await personasApi.create(form);
          await onSaved();
          onDone();
        } catch (err) {
          setError(err instanceof Error ? err.message : 'Save failed');
        }
      }}
    >
      <Field label="Name"><input style={inputStyle} value={form.name} onChange={(e) => set('name', e.target.value)} /></Field>
      <Field label="Instructions"><textarea style={{ ...inputStyle, minHeight: 140 }} value={form.content} onChange={(e) => set('content', e.target.value)} /></Field>
      {flag('is_default', 'Default persona')}
      {flag('research_mode', 'Research mode')}
      {flag('file_system_mode', 'File system mode')}
      {flag('browsing_mode', 'Browsing mode')}
      {flag('git_mode', 'Git mode')}
      {error ? <div role="alert" style={{ color: 'var(--color-rose-500)', marginBottom: 8 }}>{error}</div> : null}
      <div style={{ display: 'flex', gap: 8 }}>
        <button type="submit" className="btn-primary">Save</button>
        <button type="button" className="btn-secondary" onClick={onDone}>Cancel</button>
      </div>
    </form>
  );
}
