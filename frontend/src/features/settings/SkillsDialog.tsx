import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { skillsApi, settingsKeys, type Skill } from '../../api/settings';
import { CrudDialog } from './CrudList';
import { Field, inputStyle } from './forms';

export function SkillsDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const queryClient = useQueryClient();
  const list = useQuery({ queryKey: settingsKeys.skills, queryFn: skillsApi.list, enabled: open });
  const refresh = () => queryClient.invalidateQueries({ queryKey: settingsKeys.skills });
  return (
    <CrudDialog<Skill>
      open={open}
      onClose={onClose}
      title="Skills"
      emptyText="No skills yet. A skill is a named set of instructions you trigger with /name."
      items={list.data ?? []}
      describe={(s) => ({ id: s.id, title: `/${s.name}`, subtitle: s.description })}
      renderForm={(initial, onDone) => <SkillForm initial={initial} onDone={onDone} onSaved={refresh} />}
      onDelete={async (item) => {
        await skillsApi.remove(item.id);
        await refresh();
      }}
    />
  );
}

function SkillForm({ initial, onDone, onSaved }: { initial: Skill | null; onDone: () => void; onSaved: () => Promise<unknown> }) {
  const [name, setName] = useState(initial?.name ?? '');
  const [description, setDescription] = useState(initial?.description ?? '');
  const [instructions, setInstructions] = useState(initial?.instructions ?? '');
  const [error, setError] = useState<string | null>(null);
  return (
    <form
      onSubmit={async (e) => {
        e.preventDefault();
        if (!name.trim() || !instructions.trim()) {
          setError('Name and instructions are required.');
          return;
        }
        const body = { name: name.trim(), description: description.trim(), instructions: instructions.trim() };
        try {
          if (initial) await skillsApi.update(initial.id, body);
          else await skillsApi.create(body);
          await onSaved();
          onDone();
        } catch (err) {
          setError(err instanceof Error ? err.message : 'Save failed');
        }
      }}
    >
      <Field label="Name"><input style={inputStyle} value={name} onChange={(e) => setName(e.target.value)} /></Field>
      <Field label="Description"><input style={inputStyle} value={description} onChange={(e) => setDescription(e.target.value)} /></Field>
      <Field label="Instructions"><textarea style={{ ...inputStyle, minHeight: 140 }} value={instructions} onChange={(e) => setInstructions(e.target.value)} /></Field>
      {error ? <div role="alert" style={{ color: 'var(--color-rose-500)', marginBottom: 8 }}>{error}</div> : null}
      <div style={{ display: 'flex', gap: 8 }}>
        <button type="submit" className="btn-primary">Save</button>
        <button type="button" className="btn-secondary" onClick={onDone}>Cancel</button>
      </div>
    </form>
  );
}
