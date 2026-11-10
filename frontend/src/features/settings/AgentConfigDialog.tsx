import { useEffect, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Modal } from '../../components/ui/Modal';
import { showToast } from '../../components/ui/toast-store';
import { settingsApi, settingsKeys, type AgentConfig, type ThinkingProfile } from '../../api/settings';
import { Select } from '../../components/ui/Select';
import { Field } from '../../components/ui/Field';
import { Button } from '../../components/ui/Button';
import { agentLabel, thinkingProfileLabel } from '../../lib/labels';

const PROFILES: ThinkingProfile[] = ['general', 'precision', 'none'];

function isDirty(draft: AgentConfig | undefined, saved: AgentConfig | undefined): boolean {
  if (!draft || !saved) return false;
  return (
    draft.max_tokens !== saved.max_tokens ||
    draft.thinking_budget !== saved.thinking_budget ||
    draft.thinking_profile !== saved.thinking_profile
  );
}

/** Per-agent token budgets and thinking profile. One card per agent; one "Save changes" for all edits (F-31). */
export function AgentConfigDialog({ open, onClose, onBack }: { open: boolean; onClose: () => void; onBack?: () => void }) {
  const queryClient = useQueryClient();
  const agents = useQuery({ queryKey: settingsKeys.agents, queryFn: settingsApi.getAgents, enabled: open });
  const [draft, setDraft] = useState<Record<string, AgentConfig>>({});

  // The draft starts from the saved values each time the dialog opens and follows newer saved values
  // (a refetch after opening) while the user has not typed anything; once edited, a refetch never
  // overwrites it. Closing (Cancel, Escape, X) drops unsaved edits.
  const draftRef = useRef(draft);
  draftRef.current = draft;
  const seededFrom = useRef<Record<string, AgentConfig> | null>(null);
  useEffect(() => {
    if (!open) {
      seededFrom.current = null;
      setDraft({});
      return;
    }
    const data = agents.data;
    if (!data) return;
    const base = seededFrom.current;
    const untouched =
      base === null || Object.keys(draftRef.current).every((name) => !isDirty(draftRef.current[name], base[name]));
    if (untouched) {
      seededFrom.current = data;
      setDraft(data);
    }
  }, [open, agents.data]);

  const dirtyNames = Object.keys(draft).filter((name) => isDirty(draft[name], agents.data?.[name]));

  const save = useMutation({
    mutationFn: async () => {
      for (const name of dirtyNames) {
        await settingsApi.patchAgent(name, draft[name]!);
      }
    },
    onSuccess: () => {
      showToast('Saved', 'success');
      void queryClient.invalidateQueries({ queryKey: settingsKeys.agents });
    },
    onError: (e) => showToast(e instanceof Error ? e.message : 'Save failed', 'error'),
  });

  const footer = (
    <>
      <Button variant="secondary" onClick={onClose}>
        Cancel
      </Button>
      <Button variant="primary" disabled={dirtyNames.length === 0 || save.isPending} onClick={() => save.mutate()}>
        Save changes
      </Button>
    </>
  );

  return (
    <Modal open={open} onClose={onClose} onBack={onBack} title="Agent configuration" maxWidth={560} footer={footer}>
      <div className="agent-cards">
        {Object.entries(draft).map(([name, cfg]) => (
          <section key={name} className="agent-card">
            <h3 className="agent-card__title">{agentLabel(name)}</h3>
            <Field label="Max tokens">
              {(c) => (
                <input
                  {...c}
                  type="number"
                  className="ui-input"
                  min={256}
                  value={cfg.max_tokens}
                  onChange={(e) => setDraft({ ...draft, [name]: { ...cfg, max_tokens: Number(e.target.value) } })}
                />
              )}
            </Field>
            <Field label="Thinking budget">
              {(c) => (
                <input
                  {...c}
                  type="number"
                  className="ui-input"
                  min={0}
                  value={cfg.thinking_budget}
                  onChange={(e) => setDraft({ ...draft, [name]: { ...cfg, thinking_budget: Number(e.target.value) } })}
                />
              )}
            </Field>
            <Field label="Thinking profile">
              {(c) => (
                <Select
                  id={c.id}
                  aria-label={`${agentLabel(name)} thinking profile`}
                  value={cfg.thinking_profile}
                  options={PROFILES.map((p) => ({ value: p, label: thinkingProfileLabel(p) }))}
                  onChange={(v) => setDraft({ ...draft, [name]: { ...cfg, thinking_profile: v as ThinkingProfile } })}
                />
              )}
            </Field>
          </section>
        ))}
        {agents.isPending ? <div className="agent-cards__status">Loading…</div> : null}
      </div>
    </Modal>
  );
}
