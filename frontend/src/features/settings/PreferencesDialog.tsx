import { useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { preferencesApi, settingsKeys, type Preference } from '../../api/settings';
import { showToast } from '../../components/ui/toast-store';
import { memoryTagLabel } from '../../lib/labels';
import { CrudDialog } from './CrudList';
import { Field } from '../../components/ui/Field';
import { Button } from '../../components/ui/Button';

export function PreferencesDialog({ open, onClose, onBack }: { open: boolean; onClose: () => void; onBack?: () => void }) {
  const queryClient = useQueryClient();
  const list = useQuery({ queryKey: settingsKeys.preferences, queryFn: preferencesApi.list, enabled: open });
  const refresh = () => queryClient.invalidateQueries({ queryKey: settingsKeys.preferences });

  return (
    <CrudDialog<Preference>
      open={open}
      onClose={onClose}
      onBack={onBack}
      noun="memory"
      title="Memory & preferences"
      emptyText="Nothing saved yet. Preferences you add here are applied to every chat."
      items={list.data ?? []}
      describe={(p) => ({ id: p.id, title: p.content, subtitle: memoryTagLabel(p.tag), fullText: p.content })}
      renderForm={(initial, onDone) => <PreferenceForm initial={initial} onDone={onDone} onSaved={refresh} />}
      onDelete={async (item) => {
        await preferencesApi.remove(item.id);
        showToast('Preference removed', 'info');
        await refresh();
      }}
    />
  );
}

function PreferenceForm({ initial, onDone, onSaved }: { initial: Preference | null; onDone: () => void; onSaved: () => Promise<unknown> }) {
  const [content, setContent] = useState(initial?.content ?? '');
  const [tag, setTag] = useState(initial?.tag ?? 'preference');
  const [touched, setTouched] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const contentRef = useRef<HTMLTextAreaElement>(null);
  const contentError = content.trim() ? null : 'Write the preference in your own words.';
  const valid = !contentError && tag.trim().length > 0;

  return (
    <form
      noValidate
      onSubmit={async (e) => {
        e.preventDefault();
        if (!valid) {
          setTouched(true);
          contentRef.current?.focus();
          return;
        }
        setBusy(true);
        setError(null);
        try {
          if (initial) await preferencesApi.update(initial.id, { content: content.trim(), tag: tag.trim() });
          else await preferencesApi.create({ content: content.trim(), tag: tag.trim() });
          await onSaved();
          onDone();
        } catch (err) {
          setError(err instanceof Error ? err.message : 'Save failed');
        } finally {
          setBusy(false);
        }
      }}
    >
      <Field label="Preference" required error={touched ? contentError : null} hint={touched && contentError ? undefined : 'Applied to every chat, for example "Answer in British English".'}>
        {(c) => (
          <textarea
            {...c}
            ref={contentRef}
            className="ui-textarea"
            rows={4}
            value={content}
            onBlur={() => setTouched(true)}
            onChange={(e) => setContent(e.target.value)}
          />
        )}
      </Field>
      <Field label="Tag" required hint="Groups the memory, for example preference, project or personal info.">
        {(c) => (
          <input {...c} className="ui-input" placeholder="preference" value={tag} onChange={(e) => setTag(e.target.value)} />
        )}
      </Field>
      {error ? (
        <div role="alert" className="crud-error">
          {error}
        </div>
      ) : null}
      <div className="crud-actions">
        <Button variant="primary" type="submit" disabled={!valid || busy}>
          Save
        </Button>
        <Button variant="secondary" onClick={onDone}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
