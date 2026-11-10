import { useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { skillsApi, settingsKeys, type Skill } from '../../../api/settings';
import { trackSave } from '../../../lib/save-light';
import { CrudList, type FormFooter } from '../CrudList';
import { SettingsSection } from '../forms';
import { filterSkills } from '../../../lib/list-filter';
import { Field, Input } from '../../../components/ui/Field';

/** Skills: named recipes the model follows when asked for with a slash. */
export function SkillsSection() {
  const queryClient = useQueryClient();
  const list = useQuery({ queryKey: settingsKeys.skills, queryFn: skillsApi.list });
  const refresh = () => queryClient.invalidateQueries({ queryKey: settingsKeys.skills });
  const [query, setQuery] = useState('');
  return (
    <SettingsSection
      id="skills"
      title="Skills"
      lead="A skill is a named recipe the model follows when you ask for it with a slash."
    >
      <CrudList<Skill>
        noun="skill"
        emptyText="No skills yet."
        loading={list.isPending}
        items={filterSkills(list.data ?? [], query)}
        filtering={query.trim() !== ''}
        toolbar={
          (list.data ?? []).length > 0 ? (
            <Input
              type="search"
              aria-label="Search skills"
              placeholder="Search skills"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          ) : undefined
        }
        describe={(s) => ({
          id: s.id,
          title: `/${s.name}`,
          mono: true,
          subtitle: s.description,
          fullText: s.description,
        })}
        renderForm={(initial, onDone, footer) => (
          <SkillForm initial={initial} onDone={onDone} onSaved={refresh} footer={footer} />
        )}
        onDelete={async (item) => {
          await trackSave(skillsApi.remove(item.id));
          await refresh();
        }}
      />
    </SettingsSection>
  );
}

interface SkillDraft {
  name: string;
  description: string;
  instructions: string;
}

/** Skill names are lowercase words joined by hyphens; the `/` prefix is added by the UI. */
const NAME_PATTERN = /^[a-z0-9][a-z0-9-]*$/;

function validateSkill(draft: SkillDraft): Partial<Record<keyof SkillDraft, string>> {
  const errors: Partial<Record<keyof SkillDraft, string>> = {};
  const name = draft.name.trim();
  if (!name) errors.name = 'Enter a name, for example my-skill.';
  else if (!NAME_PATTERN.test(name)) errors.name = 'Use lowercase letters, numbers and hyphens only.';
  if (!draft.description.trim()) errors.description = 'Describe what the skill does.';
  if (!draft.instructions.trim()) errors.instructions = 'Describe what the assistant should do.';
  return errors;
}

function SkillForm({
  initial,
  onDone,
  onSaved,
  footer,
}: {
  initial: Skill | null;
  onDone: () => void;
  onSaved: () => Promise<unknown>;
  footer: FormFooter;
}) {
  const [draft, setDraft] = useState<SkillDraft>({
    name: initial?.name ?? '',
    description: initial?.description ?? '',
    instructions: initial?.instructions ?? '',
  });
  const [touched, setTouched] = useState<Partial<Record<keyof SkillDraft, boolean>>>({});
  const [error, setError] = useState<string | null>(null);
  const nameRef = useRef<HTMLInputElement>(null);
  const instructionsRef = useRef<HTMLTextAreaElement>(null);
  const errors = validateSkill(draft);
  const valid = Object.keys(errors).length === 0;
  const shown = (key: keyof SkillDraft) => (touched[key] ? errors[key] ?? null : null);
  const set = (key: keyof SkillDraft, value: string) => setDraft((d) => ({ ...d, [key]: value }));
  const { setCanSave } = footer;
  useEffect(() => setCanSave(valid), [valid, setCanSave]);

  return (
    <form
      id={footer.formId}
      noValidate
      onSubmit={async (e) => {
        e.preventDefault();
        if (!valid) {
          setTouched({ name: true, description: true, instructions: true });
          (errors.name ? nameRef : instructionsRef).current?.focus();
          return;
        }
        const body = { name: draft.name.trim(), description: draft.description.trim(), instructions: draft.instructions.trim() };
        try {
          await trackSave(initial ? skillsApi.update(initial.id, body) : skillsApi.create(body));
          await onSaved();
          onDone();
        } catch (err) {
          setError(err instanceof Error ? err.message : 'The skill could not be saved. Try again.');
        }
      }}
    >
      <Field label="Name" required error={shown('name')} hint={shown('name') ? undefined : 'Typed after a slash in the message box.'}>
        {(c) => (
          <div className="skill-field">
            <span className="skill-field__prefix" aria-hidden="true">/</span>
            <input
              {...c}
              ref={nameRef}
              className="ui-input"
              placeholder="my-skill"
              value={draft.name}
              onBlur={() => setTouched((t) => ({ ...t, name: true }))}
              onChange={(e) => set('name', e.target.value)}
            />
          </div>
        )}
      </Field>
      <Field label="Description" required error={shown('description')} hint={shown('description') ? undefined : 'A short summary shown in the skill list.'}>
        {(c) => (
          <input {...c} className="ui-input" placeholder="Summarise a long document" value={draft.description} onBlur={() => setTouched((t) => ({ ...t, description: true }))} onChange={(e) => set('description', e.target.value)} />
        )}
      </Field>
      <Field label="Instructions" required error={shown('instructions')} hint={shown('instructions') ? undefined : 'The prompt sent when you run the skill.'}>
        {(c) => (
          <textarea
            {...c}
            ref={instructionsRef}
            className="ui-textarea"
            rows={6}
            placeholder="Read the attached text and list the three main points."
            value={draft.instructions}
            onBlur={() => setTouched((t) => ({ ...t, instructions: true }))}
            onChange={(e) => set('instructions', e.target.value)}
          />
        )}
      </Field>
      {error ? (
        <div role="alert" className="crud-error">
          {error}
        </div>
      ) : null}
    </form>
  );
}
