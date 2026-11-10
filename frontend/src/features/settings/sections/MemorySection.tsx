import { useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { preferencesApi, settingsKeys, type Preference } from '../../../api/settings';
import { showToast } from '../../../components/ui/toast-store';
import { memoryTagLabel } from '../../../lib/labels';
import { Button } from '../../../components/ui/Button';
import { ConfirmDialog } from '../../../components/ui/ConfirmDialog';
import { trackSave } from '../../../lib/save-light';
import { CrudList, type FormFooter } from '../CrudList';
import { SettingsSection, SubHead } from '../forms';
import { Select } from '../../../components/ui/Select';
import { filterPreferences, tagsOf, type PreferenceSort } from '../../../lib/list-filter';
import { Field, Input } from '../../../components/ui/Field';

/** Memory: what the model should remember about the person across chats. */
export function MemorySection() {
  const queryClient = useQueryClient();
  const list = useQuery({ queryKey: settingsKeys.preferences, queryFn: preferencesApi.list });
  const refresh = () => queryClient.invalidateQueries({ queryKey: settingsKeys.preferences });
  const [query, setQuery] = useState('');
  const [tag, setTag] = useState('');
  const [sort, setSort] = useState<PreferenceSort>('newest');
  const [confirmReset, setConfirmReset] = useState(false);
  const all = list.data ?? [];
  const shown = filterPreferences(all, { query, tag, sort });
  const filtering = query.trim() !== '' || tag !== '';

  async function reset() {
    try {
      await trackSave(preferencesApi.reset());
      showToast('Memory reset', 'success');
      await refresh();
    } catch (err) {
      showToast(
        err instanceof Error ? err.message : 'Memory could not be reset. Try again.',
        'error',
      );
    }
  }

  return (
    <SettingsSection
      id="memory"
      title="Memory"
      lead="Things the model should remember about you across chats."
    >
      <CrudList<Preference>
        noun="preference"
        emptyText="Nothing saved yet."
        loading={list.isPending}
        items={shown}
        filtering={filtering}
        toolbar={
          all.length > 0 ? (
            <>
              <Input
                type="search"
                aria-label="Search memory"
                placeholder="Search memory"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
              <Select
                aria-label="Filter by tag"
                value={tag}
                onChange={setTag}
                options={[
                  { value: '', label: 'All tags' },
                  ...tagsOf(all).map((t) => ({ value: t, label: memoryTagLabel(t) })),
                ]}
              />
              <Select
                aria-label="Order"
                value={sort}
                onChange={(v) => setSort(v === 'oldest' ? 'oldest' : 'newest')}
                options={[
                  { value: 'newest', label: 'Newest first' },
                  { value: 'oldest', label: 'Oldest first' },
                ]}
              />
            </>
          ) : undefined
        }
        describe={(p) => ({
          id: p.id,
          title: p.content,
          tag: memoryTagLabel(p.tag),
          fullText: p.content,
        })}
        renderForm={(initial, onDone, footer) => (
          <PreferenceForm initial={initial} onDone={onDone} onSaved={refresh} footer={footer} />
        )}
        onDelete={async (item) => {
          await trackSave(preferencesApi.remove(item.id));
          await refresh();
        }}
      />
      <SubHead danger>Danger zone</SubHead>
      <div className="set-row">
        <div className="set-row__text">
          <div className="set-row__label">Reset memory</div>
          <div className="ui-hint">Forgets everything saved here. This cannot be undone.</div>
        </div>
        <Button variant="danger" onClick={() => setConfirmReset(true)}>
          Reset memory
        </Button>
      </div>
      <ConfirmDialog
        open={confirmReset}
        title="Reset memory?"
        message="Everything saved in memory will be forgotten. This cannot be undone."
        confirmLabel="Reset memory"
        danger
        onCancel={() => setConfirmReset(false)}
        onConfirm={() => {
          setConfirmReset(false);
          void reset();
        }}
      />
    </SettingsSection>
  );
}

function PreferenceForm({
  initial,
  onDone,
  onSaved,
  footer,
}: {
  initial: Preference | null;
  onDone: () => void;
  onSaved: () => Promise<unknown>;
  footer: FormFooter;
}) {
  const [content, setContent] = useState(initial?.content ?? '');
  const [tag, setTag] = useState(initial?.tag ?? 'preference');
  const [touched, setTouched] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const contentRef = useRef<HTMLTextAreaElement>(null);
  const contentError = content.trim() ? null : 'Write the preference in your own words.';
  const valid = !contentError && tag.trim().length > 0;
  const { setCanSave } = footer;
  useEffect(() => setCanSave(valid && !busy), [valid, busy, setCanSave]);

  return (
    <form
      id={footer.formId}
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
          const body = { content: content.trim(), tag: tag.trim() };
          await trackSave(
            initial ? preferencesApi.update(initial.id, body) : preferencesApi.create(body),
          );
          await onSaved();
          onDone();
        } catch (err) {
          setError(
            err instanceof Error ? err.message : 'The preference could not be saved. Try again.',
          );
        } finally {
          setBusy(false);
        }
      }}
    >
      <Field
        label="Preference"
        required
        error={touched ? contentError : null}
        hint={
          touched && contentError
            ? undefined
            : 'Applied to every chat, for example "Answer in British English".'
        }
      >
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
      <Field
        label="Tag"
        required
        hint="Groups what is remembered, for example preference, project or personal info."
      >
        {(c) => (
          <input
            {...c}
            className="ui-input"
            placeholder="preference"
            value={tag}
            onChange={(e) => setTag(e.target.value)}
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
