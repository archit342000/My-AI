import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Modal } from '../../components/ui/Modal';
import { showToast } from '../../components/ui/toast-store';
import { settingsApi, settingsKeys, type AgentConfig, type ThinkingProfile } from '../../api/settings';
import { Field, Section, inputStyle } from './forms';

const PROFILES: ThinkingProfile[] = ['general', 'precision', 'none'];

/** Per-agent token budgets and thinking profile for the backend tool agents. */
export function AgentConfigDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const queryClient = useQueryClient();
  const agents = useQuery({ queryKey: settingsKeys.agents, queryFn: settingsApi.getAgents, enabled: open });
  const [draft, setDraft] = useState<Record<string, AgentConfig>>({});

  useEffect(() => {
    if (agents.data) setDraft(agents.data);
  }, [agents.data]);

  const save = useMutation({
    mutationFn: async (name: string) => settingsApi.patchAgent(name, draft[name]!),
    onSuccess: (_d, name) => {
      showToast(`${name.replace(/_/g, ' ')} saved`, 'success');
      void queryClient.invalidateQueries({ queryKey: settingsKeys.agents });
    },
    onError: (e) => showToast(e instanceof Error ? e.message : 'Save failed', 'error'),
  });

  return (
    <Modal open={open} onClose={onClose} title="Agent configuration" maxWidth={560}>
      {Object.entries(draft).map(([name, cfg]) => (
        <Section key={name} title={name.replace(/_/g, ' ')}>
          <Field label="Max tokens">
            <input type="number" min={256} style={inputStyle} value={cfg.max_tokens} onChange={(e) => setDraft({ ...draft, [name]: { ...cfg, max_tokens: Number(e.target.value) } })} />
          </Field>
          <Field label="Thinking budget">
            <input type="number" min={0} style={inputStyle} value={cfg.thinking_budget} onChange={(e) => setDraft({ ...draft, [name]: { ...cfg, thinking_budget: Number(e.target.value) } })} />
          </Field>
          <Field label="Thinking profile">
            <select style={inputStyle} value={cfg.thinking_profile} onChange={(e) => setDraft({ ...draft, [name]: { ...cfg, thinking_profile: e.target.value as ThinkingProfile } })}>
              {PROFILES.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
          </Field>
          <button type="button" className="btn-primary" onClick={() => save.mutate(name)} disabled={save.isPending}>Save</button>
        </Section>
      ))}
      {agents.isPending ? <div style={{ color: 'var(--content-muted)' }}>Loading…</div> : null}
    </Modal>
  );
}
