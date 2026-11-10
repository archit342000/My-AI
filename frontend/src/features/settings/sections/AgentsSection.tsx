import { useEffect, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  settingsApi,
  settingsKeys,
  SETTINGS_STALE_MS,
  type AgentConfig,
  type ThinkingProfile,
} from '../../../api/settings';
import { Field, Input } from '../../../components/ui/Field';
import { SegmentedControl } from '../../../components/ui/SegmentedControl';
import { Select } from '../../../components/ui/Select';
import { showToast } from '../../../components/ui/toast-store';
import { agentLabel, thinkingProfileLabel } from '../../../lib/labels';
import { trackSave } from '../../../lib/save-light';
import { SettingRow, SettingsSection, SubHead } from '../forms';
import { GitSettings } from '../GitSettingsSection';

const PROFILES: ThinkingProfile[] = ['general', 'precision', 'none'];
const MIN_TOKENS = 256;

type StealthLevel = 'minimal' | 'advanced';

/** One agent's limits. A number is kept when its box is left (or Enter is pressed); a choice at once. */
function AgentCard({
  name,
  saved,
  onSave,
}: {
  name: string;
  saved: AgentConfig;
  onSave: (next: AgentConfig) => void;
}) {
  const [tokens, setTokens] = useState(String(saved.max_tokens));
  const [budget, setBudget] = useState(String(saved.thinking_budget));
  // The boxes follow the server's values, except the one being typed in.
  const editing = useRef<'tokens' | 'budget' | null>(null);
  useEffect(() => {
    if (editing.current !== 'tokens') setTokens(String(saved.max_tokens));
    if (editing.current !== 'budget') setBudget(String(saved.thinking_budget));
  }, [saved.max_tokens, saved.thinking_budget]);

  const tokensError =
    Number.isFinite(Number(tokens)) && Number(tokens) >= MIN_TOKENS
      ? null
      : `At least ${MIN_TOKENS} tokens.`;
  const budgetError =
    budget.trim() !== '' && Number.isFinite(Number(budget)) && Number(budget) >= 0
      ? null
      : 'Zero or more tokens.';

  function commit() {
    editing.current = null;
    if (tokensError || budgetError) return;
    const next = { ...saved, max_tokens: Number(tokens), thinking_budget: Number(budget) };
    if (next.max_tokens !== saved.max_tokens || next.thinking_budget !== saved.thinking_budget)
      onSave(next);
  }
  const label = agentLabel(name);

  return (
    <section className="agent" aria-label={label}>
      <h3 className="set-row__label">{label}</h3>
      <div className="field-grid">
        <Field label="Longest answer (tokens)" error={tokensError}>
          {(c) => (
            <Input
              {...c}
              type="number"
              min={MIN_TOKENS}
              step={256}
              value={tokens}
              onFocus={() => (editing.current = 'tokens')}
              onChange={(e) => setTokens(e.target.value)}
              onBlur={commit}
              onKeyDown={(e) => e.key === 'Enter' && commit()}
            />
          )}
        </Field>
        <Field label="Thinking budget (tokens)" error={budgetError}>
          {(c) => (
            <Input
              {...c}
              type="number"
              min={0}
              step={256}
              value={budget}
              onFocus={() => (editing.current = 'budget')}
              onChange={(e) => setBudget(e.target.value)}
              onBlur={commit}
              onKeyDown={(e) => e.key === 'Enter' && commit()}
            />
          )}
        </Field>
        <Field label="Thinking profile">
          {(c) => (
            <Select
              id={c.id}
              aria-label={`${label} thinking profile`}
              value={saved.thinking_profile}
              options={PROFILES.map((p) => ({ value: p, label: thinkingProfileLabel(p) }))}
              onChange={(v) => onSave({ ...saved, thinking_profile: v as ThinkingProfile })}
            />
          )}
        </Field>
      </div>
    </section>
  );
}

/**
 * Agents (admin): limits for the helpers that work on longer tasks, how the AI's browser presents
 * itself, and what the git agent may do. Everything here is kept the moment it changes.
 */
export function AgentsSection() {
  const queryClient = useQueryClient();
  const agents = useQuery({ queryKey: settingsKeys.agents, queryFn: settingsApi.getAgents });
  // Counts failed saves: the cards are rebuilt from the server's values, so a refused number goes back.
  const [resets, setResets] = useState(0);
  const browser = useQuery({
    queryKey: settingsKeys.browser,
    queryFn: settingsApi.getBrowser,
    staleTime: SETTINGS_STALE_MS,
  });
  const system = useQuery({
    queryKey: settingsKeys.system,
    queryFn: settingsApi.getSystem,
    staleTime: SETTINGS_STALE_MS,
  });

  const saveAgent = useMutation({
    mutationFn: ({ name, config }: { name: string; config: AgentConfig }) =>
      trackSave(settingsApi.patchAgent(name, config)),
    // Shown at once; put back from the server if the save fails.
    onMutate: ({ name, config }) => {
      const before = queryClient.getQueryData<Record<string, AgentConfig>>(settingsKeys.agents);
      queryClient.setQueryData<Record<string, AgentConfig>>(settingsKeys.agents, (old) =>
        old ? { ...old, [name]: config } : old,
      );
      return { before };
    },
    onError: (e, { name }, context) => {
      if (context?.before) queryClient.setQueryData(settingsKeys.agents, context.before);
      setResets((n) => n + 1);
      showToast(
        e instanceof Error ? e.message : `${agentLabel(name)} could not be saved. Try again.`,
        'error',
      );
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: settingsKeys.agents }),
  });

  const saveStealth = useMutation({
    mutationFn: (level: StealthLevel) => trackSave(settingsApi.setBrowser(level)),
    onMutate: (level) => {
      const before = queryClient.getQueryData<{ stealth_level: StealthLevel }>(
        settingsKeys.browser,
      );
      queryClient.setQueryData(settingsKeys.browser, { stealth_level: level });
      return { before };
    },
    onError: (e, _level, context) => {
      if (context?.before) queryClient.setQueryData(settingsKeys.browser, context.before);
      showToast(
        e instanceof Error ? e.message : 'Browser stealth could not be saved. Try again.',
        'error',
      );
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: settingsKeys.browser }),
  });

  return (
    <SettingsSection
      id="agents"
      title="Agents"
      lead="Limits for the helpers that work on longer tasks."
    >
      {Object.entries(agents.data ?? {}).map(([name, config]) => (
        <AgentCard
          key={`${name}:${resets}`}
          name={name}
          saved={config}
          onSave={(next) => saveAgent.mutate({ name, config: next })}
        />
      ))}
      {agents.isPending ? (
        <p className="ui-hint crud-none" role="status">
          Loading the agents
        </p>
      ) : null}
      {agents.isError ? (
        <p className="ui-hint crud-none" role="alert">
          The agents could not be loaded. Try again in a moment.
        </p>
      ) : null}

      <SubHead>The AI's browser</SubHead>
      <SettingRow
        label="Browser stealth"
        hint="How hard the AI's browser tries to pass as a person's. Advanced gets into more sites, and is slower."
        wide
      >
        {() => (
          <SegmentedControl
            label="Browser stealth"
            value={browser.data?.stealth_level ?? 'minimal'}
            options={[
              { value: 'minimal', label: 'Minimal' },
              { value: 'advanced', label: 'Advanced' },
            ]}
            onChange={(v) => saveStealth.mutate(v as StealthLevel)}
          />
        )}
      </SettingRow>

      {system.data ? (
        <>
          <SubHead>Git agent</SubHead>
          <GitSettings system={system.data} />
        </>
      ) : null}
    </SettingsSection>
  );
}
