import { useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { personasApi, settingsKeys, type Persona } from '../../../api/settings';
import { trackSave } from '../../../lib/save-light';
import { CrudList, type FormFooter } from '../CrudList';
import { SettingsSection } from '../forms';
import { Field } from '../../../components/ui/Field';
import { Toggle } from '../../../components/ui/Toggle';
import { firstSentencePreview } from '../../../lib/preview-text';

type PersonaBody = Omit<Persona, 'id'>;
type FlagKey = 'is_default' | 'research_mode' | 'file_system_mode' | 'browsing_mode';

const EMPTY: PersonaBody = {
  name: '',
  content: '',
  is_default: 0,
  research_mode: 0,
  file_system_mode: 0,
  browsing_mode: 0,
};

/**
 * Only the flags the persona API stores. It ignores git and code-execution mode on input, and an
 * edit resets those two server-side values to their defaults (a backend follow-up).
 */
const FLAGS: Array<{ key: FlagKey; label: string; description: string }> = [
  { key: 'is_default', label: 'Default persona', description: 'Used for new chats unless another persona is chosen.' },
  { key: 'research_mode', label: 'Research mode', description: 'Encourages multi-source research before answering.' },
  { key: 'file_system_mode', label: 'File system mode', description: 'Allows reading and writing workspace files.' },
  { key: 'browsing_mode', label: 'Browsing mode', description: 'Allows opening web pages with the browser tool.' },
];

/** Personas: standing instructions that can be switched on for a chat. */
export function PersonasSection() {
  const queryClient = useQueryClient();
  const list = useQuery({ queryKey: settingsKeys.personas, queryFn: personasApi.list });
  const refresh = () => queryClient.invalidateQueries({ queryKey: settingsKeys.personas });
  return (
    <SettingsSection
      id="personas"
      title="Personas"
      lead="A persona is a set of standing instructions you can switch on for a chat."
    >
      <CrudList<Persona>
        noun="persona"
        emptyText="No personas yet."
        loading={list.isPending}
        items={list.data ?? []}
        describe={(p) => ({
          id: p.id,
          title: p.name,
          tag: p.is_default ? 'Default' : undefined,
          subtitle: firstSentencePreview(p.content),
          fullText: p.content,
        })}
        renderForm={(initial, onDone, footer) => (
          <PersonaForm initial={initial} onDone={onDone} onSaved={refresh} footer={footer} />
        )}
        onDelete={async (item) => {
          await trackSave(personasApi.remove(item.id));
          await refresh();
        }}
      />
    </SettingsSection>
  );
}

/** The fields the persona API stores, taken from a persona row. */
function storedFields(row: Persona): PersonaBody {
  return {
    name: row.name,
    content: row.content,
    is_default: row.is_default,
    research_mode: row.research_mode,
    file_system_mode: row.file_system_mode,
    browsing_mode: row.browsing_mode,
  };
}

/** Validation rules for a persona; returns one message per invalid field. */
function validatePersona(form: PersonaBody): { name?: string; content?: string } {
  const errors: { name?: string; content?: string } = {};
  if (!form.name.trim()) errors.name = 'Enter a name for this persona.';
  if (!form.content.trim()) errors.content = 'Describe the role and instructions.';
  return errors;
}

function PersonaForm({
  initial,
  onDone,
  onSaved,
  footer,
}: {
  initial: Persona | null;
  onDone: () => void;
  onSaved: () => Promise<unknown>;
  footer: FormFooter;
}) {
  // Only the stored fields go into the form, so nothing else the row carries is sent back.
  const [form, setForm] = useState<PersonaBody>(initial ? storedFields(initial) : EMPTY);
  const [touched, setTouched] = useState<{ name?: boolean; content?: boolean }>({});
  const [error, setError] = useState<string | null>(null);
  const nameRef = useRef<HTMLInputElement>(null);
  const contentRef = useRef<HTMLTextAreaElement>(null);
  const errors = validatePersona(form);
  const valid = Object.keys(errors).length === 0;
  const set = <K extends keyof PersonaBody>(key: K, value: PersonaBody[K]) => setForm((f) => ({ ...f, [key]: value }));
  const { setCanSave } = footer;
  useEffect(() => setCanSave(valid), [valid, setCanSave]);

  return (
    <form
      id={footer.formId}
      noValidate
      onSubmit={async (e) => {
        e.preventDefault();
        if (!valid) {
          setTouched({ name: true, content: true });
          (errors.name ? nameRef : contentRef).current?.focus();
          return;
        }
        try {
          await trackSave(
            initial ? personasApi.update(initial.id, form) : personasApi.create(form),
          );
          await onSaved();
          onDone();
        } catch (err) {
          setError(err instanceof Error ? err.message : 'The persona could not be saved. Try again.');
        }
      }}
    >
      <Field
        label="Name"
        required
        error={touched.name ? errors.name ?? null : null}
        hint={touched.name && errors.name ? undefined : 'Shown in this list and where you pick a persona.'}
      >
        {(c) => (
          <input
            {...c}
            ref={nameRef}
            className="ui-input"
            placeholder="For example: Careful reviewer"
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
    </form>
  );
}
