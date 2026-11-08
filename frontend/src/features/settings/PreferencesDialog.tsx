import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { preferencesApi, settingsKeys, type Preference } from '../../api/settings';
import { showToast } from '../../components/ui/toast-store';
import { CrudDialog } from './CrudList';
import { Field, inputStyle } from './forms';

export function PreferencesDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const queryClient = useQueryClient();
  const list = useQuery({ queryKey: settingsKeys.preferences, queryFn: preferencesApi.list, enabled: open });
  const refresh = () => queryClient.invalidateQueries({ queryKey: settingsKeys.preferences });

  return (
    <CrudDialog<Preference>
      open={open}
      onClose={onClose}
      title="Memory & preferences"
      emptyText="Nothing saved yet. Preferences you add here are applied to every chat."
      items={list.data ?? []}
      describe={(p) => ({ id: p.id, title: p.content, subtitle: p.tag })}
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
  const [busy, setBusy] = useState(false);
  return (
    <form
      onSubmit={async (e) => {
        e.preventDefault();
        if (!content.trim()) return;
        setBusy(true);
        try {
          if (initial) await preferencesApi.update(initial.id, { content: content.trim(), tag });
          else await preferencesApi.create({ content: content.trim(), tag });
          await onSaved();
          onDone();
        } finally {
          setBusy(false);
        }
      }}
    >
      <Field label="Preference">
        <textarea style={{ ...inputStyle, minHeight: 100 }} value={content} onChange={(e) => setContent(e.target.value)} />
      </Field>
      <Field label="Tag">
        <input style={inputStyle} value={tag} onChange={(e) => setTag(e.target.value)} />
      </Field>
      <div style={{ display: 'flex', gap: 8 }}>
        <button type="submit" className="btn-primary" disabled={busy}>Save</button>
        <button type="button" className="btn-secondary" onClick={onDone}>Cancel</button>
      </div>
    </form>
  );
}
