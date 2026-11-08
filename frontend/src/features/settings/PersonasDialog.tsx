import { useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { personasApi, settingsKeys, type Persona } from '../../api/settings';
import { CrudDialog } from './CrudList';
import { Field } from '../../components/ui/Field';
import { Toggle } from '../../components/ui/Toggle';
import { Button } from '../../components/ui/Button';
import { firstSentencePreview } from '../../lib/preview-text';

type PersonaBody = Omit<Persona, 'id'>;
type FlagKey = 'is_default' | 'research_mode' | 'file_system_mode' | 'browsing_mode' | 'git_mode';

const EMPTY: PersonaBody = {
  name: '',
  content: '',
  is_default: 0,
  research_mode: 0,
  file_system_mode: 0,
  browsing_mode: 0,
  git_mode: 0,
};

const FLAGS: Array<{ key: FlagKey; label: string; description: string }> = [
  { key: 'is_default', label: 'Default persona', description: 'Used for new chats unless another persona is chosen.' },
  { key: 'research_mode', label: 'Research mode', description: 'Encourages multi-source research before answering.' },
  { key: 'file_system_mode', label: 'File system mode', description: 'Allows reading and writing workspace files.' },
  { key: 'browsing_mode', label: 'Browsing mode', description: 'Allows opening web pages with the browser tool.' },
  { key: 'git_mode', label: 'Git mode', description: 'Allows git commands in the workspace.' },
];

export function PersonasDialog({ open, onClose, onBack }: { open: boolean; onClose: () => void; onBack?: () => void }) {
  const queryClient = useQueryClient();
  const list = useQuery({ queryKey: settingsKeys.personas, queryFn: personasApi.list, enabled: open });
  const refresh = () => queryClient.invalidateQueries({ queryKey: settingsKeys.personas });
  return (
    <CrudDialog<Persona>
      open={open}
      onClose={onClose}
      onBack={onBack}
      noun="persona"
      title="Personas"
      emptyText="No personas yet. A persona sets the assistant's role and instructions."
      items={list.data ?? []}
      describe={(p) => ({
        id: p.id,
        title: p.name + (p.is_default ? ' (default)' : ''),
        subtitle: firstSentencePreview(p.content),
        fullText: p.content,
      })}
      renderForm={(initial, onDone) => <PersonaForm initial={initial} onDone={onDone} onSaved={refresh} />}
      onDelete={async (item) => {
        await personasApi.remove(item.id);
        await refresh();
      }}
    />
  );
}

/** Validation rules for a persona; returns one message per invalid field. */
function validatePersona(form: PersonaBody): { name?: string; content?: string } {
  const errors: { name?: string; content?: string } = {};
  if (!form.name.trim()) errors.name = 'Enter a name for this persona.';
  if (!form.content.trim()) errors.content = 'Describe the role and instructions.';
  return errors;
}

function PersonaForm({ initial, onDone, onSaved }: { initial: Persona | null; onDone: () => void; onSaved: () => Promise<unknown> }) {
  const [form, setForm] = useState<PersonaBody>(initial ? { ...EMPTY, ...initial } : EMPTY);
  const [touched, setTouched] = useState<{ name?: boolean; content?: boolean }>({});
  const [error, setError] = useState<string | null>(null);
  const nameRef = useRef<HTMLInputElement>(null);
  const contentRef = useRef<HTMLTextAreaElement>(null);
  const errors = validatePersona(form);
  const valid = Object.keys(errors).length === 0;
  const set = <K extends keyof PersonaBody>(key: K, value: PersonaBody[K]) => setForm((f) => ({ ...f, [key]: value }));

  return (
    <form
      noValidate
      onSubmit={async (e) => {
        e.preventDefault();
        if (!valid) {
          setTouched({ name: true, content: true });
          (errors.name ? nameRef : contentRef).current?.focus();
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
      <Field
        label="Name"
        required
        error={touched.name ? errors.name ?? null : null}
        hint={touched.name && errors.name ? undefined : 'Shown in the persona list and the chat settings.'}
      >
        {(c) => (
          <input
            {...c}
            ref={nameRef}
            className="ui-input"
            placeholder="e.g. Code reviewer"
            value={form.name}
            onBlur={() => setTouched((t) => ({ ...t, name: true }))}
            onChange={(e) => set('name', e.target.value)}
          />
        )}
      </Field>
      <Field
        label="Instructions"
        required
        error={touched.content ? errors.content ?? null : null}
        hint="Sets the assistant's role and how it should respond."
      >
        {(c) => (
          <textarea
            {...c}
            ref={contentRef}
            className="ui-textarea"
            rows={6}
            placeholder="You are a careful reviewer who explains each finding."
            value={form.content}
            onBlur={() => setTouched((t) => ({ ...t, content: true }))}
            onChange={(e) => set('content', e.target.value)}
          />
        )}
      </Field>
      <div className="crud-flags">
        {FLAGS.map(({ key, label, description }) => (
          <Toggle
            key={key}
            checked={Boolean(form[key])}
            onChange={(v) => set(key, v ? 1 : 0)}
            label={label}
            description={description}
          />
        ))}
      </div>
      {error ? (
        <div role="alert" className="crud-error">
          {error}
        </div>
      ) : null}
      <div className="crud-actions">
        <Button variant="primary" type="submit" disabled={!valid}>
          Save
        </Button>
        <Button variant="secondary" onClick={onDone}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
