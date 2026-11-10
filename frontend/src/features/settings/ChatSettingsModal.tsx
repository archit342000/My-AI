import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Modal } from '../../components/ui/Modal';
import { Select } from '../../components/ui/Select';
import { Slider } from '../../components/ui/Slider';
import { Field as UiField } from '../../components/ui/Field';
import { Toggle } from '../../components/ui/Toggle';
import { Button } from '../../components/ui/Button';
import { modelSelectOptions } from '../../lib/model-options';
import { thinkingProfileLabel } from '../../lib/labels';
import { modelsApi, personasApi, settingsKeys } from '../../api/settings';
import { useSettingsStore } from '../../state/settings-store';
import { Status } from './forms';
import { SETTINGS_STALE_MS } from '../../api/settings';

type Tab = 'general' | 'persona' | 'parameters';

/** Starting value when a sampling parameter leaves the model-default state. */
const TEMPERATURE_START = 1;
const TOP_P_START = 1;
/** How long a status message stays visible. */
const STATUS_MS = 3000;

/**
 * Optional sampling value: unset means "model default". Shows a Set button while unset and a
 * slider plus a reset link while set (F-27).
 */
function OptionalSlider({
  label,
  value,
  start,
  min,
  max,
  step,
  onChange,
}: {
  label: string;
  value: number | undefined;
  start: number;
  min: number;
  max: number;
  step: number;
  onChange: (value: number | undefined) => void;
}) {
  if (value === undefined) {
    return (
      <div className="chat-settings__default">
        <span>Using the model default</span>
        <Button size="sm" variant="secondary" onClick={() => onChange(start)}>
          Set {label.toLowerCase()}
        </Button>
      </div>
    );
  }
  return (
    <div className="chat-settings__optional">
      <Slider label={label} value={value} min={min} max={max} step={step} onChange={(v) => onChange(v)} />
      <Button size="sm" variant="ghost" onClick={() => onChange(undefined)}>
        Reset to model default
      </Button>
    </div>
  );
}

/** Chat Settings: model, thinking, sampling parameters and persona (legacy tabs). */
export function ChatSettingsModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [tab, setTab] = useState<Tab>('general');
  const model = useSettingsStore((s) => s.model);
  const userPreferences = useSettingsStore((s) => s.userPreferences);
  const sampling = useSettingsStore((s) => s.sampling);
  const personaId = useSettingsStore((s) => s.personaId);
  const setModel = useSettingsStore((s) => s.setModel);
  const setUserPreferences = useSettingsStore((s) => s.setUserPreferences);
  const setSampling = useSettingsStore((s) => s.setSampling);
  const setPersona = useSettingsStore((s) => s.setPersona);
  const models = useQuery({
    queryKey: settingsKeys.models,
    queryFn: modelsApi.list,
    enabled: open,
    staleTime: SETTINGS_STALE_MS,
  });
  const personas = useQuery({
    queryKey: settingsKeys.personas,
    queryFn: personasApi.list,
    enabled: open,
    staleTime: SETTINGS_STALE_MS,
  });
  // `id` changes with every message, so picking the same value again restarts the timer.
  const [status, setStatus] = useState<{ text: string; id: number } | null>(null);
  const saved = status?.text ?? null;
  const setSaved = (text: string) => setStatus((prev) => ({ text, id: (prev?.id ?? 0) + 1 }));
  // The status line goes away by itself.
  useEffect(() => {
    if (!status) return undefined;
    const timer = window.setTimeout(() => setStatus(null), STATUS_MS);
    return () => window.clearTimeout(timer);
  }, [status]);

  const tabs: Array<[Tab, string]> = [
    ['general', 'General'],
    ['persona', 'Persona'],
    ['parameters', 'Parameters'],
  ];

  return (
    <Modal open={open} onClose={onClose} title="Chat Settings" maxWidth={640}>
      <div role="tablist" className="chat-settings__tabs">
        {tabs.map(([key, label]) => (
          <Button
            key={key}
            role="tab"
            aria-selected={tab === key}
            variant={tab === key ? 'primary' : 'ghost'}
            size="sm"
            onClick={() => setTab(key)}
          >
            {label}
          </Button>
        ))}
      </div>

      {/* Fixed minimum height (tallest tab) so the modal does not jump between tabs (F-26). */}
      <div className="chat-settings__body">
        {tab === 'general' ? (
          <>
            <UiField label="Model" hint="Used for the next message.">
              {(c) => (
                <Select
                  id={c.id}
                  aria-label="Model"
                  placeholder="Select a model"
                  searchable
                  searchPlaceholder="Search models"
                  value={model ?? ''}
                  options={modelSelectOptions(models.data ?? [])}
                  onChange={(id) => {
                    setModel(id, id);
                    setSaved('Model updated');
                  }}
                />
              )}
            </UiField>
            <Toggle
              checked={userPreferences}
              onChange={(v) => setUserPreferences(v)}
              label="User preferences"
              description="Personalise responses using your profile and learned preferences."
            />
            <UiField label="Thinking profile">
              {(c) => (
                <Select
                  id={c.id}
                  aria-label="Thinking profile"
                  value={sampling.thinking_profile}
                  options={['general', 'precision', 'none'].map((p) => ({ value: p, label: thinkingProfileLabel(p) }))}
                  onChange={(v) => setSampling({ thinking_profile: v })}
                />
              )}
            </UiField>
          </>
        ) : null}

        {tab === 'persona' ? (
          <UiField label="Persona" hint="Applies its instructions to new messages.">
            {(c) => (
              <Select
                id={c.id}
                aria-label="Persona"
                value={personaId ?? ''}
                options={[{ value: '', label: 'None' }, ...(personas.data ?? []).map((p) => ({ value: p.id, label: p.name }))]}
                onChange={(v) => setPersona(v || null)}
              />
            )}
          </UiField>
        ) : null}

        {tab === 'parameters' ? (
          <>
            <UiField label="Max tokens">
              {() => (
                <Slider
                  label="Max tokens"
                  value={sampling.max_tokens}
                  min={256}
                  max={32768}
                  step={256}
                  decimals={0}
                  onChange={(v) => setSampling({ max_tokens: v })}
                />
              )}
            </UiField>
            <UiField label="Thinking budget">
              {() => (
                <Slider
                  label="Thinking budget"
                  value={sampling.thinking_budget_tokens}
                  min={0}
                  max={8000}
                  step={100}
                  decimals={0}
                  onChange={(v) => setSampling({ thinking_budget_tokens: v })}
                />
              )}
            </UiField>
            <UiField label="Temperature">
              {() => (
                <OptionalSlider
                  label="Temperature"
                  value={sampling.temperature}
                  start={TEMPERATURE_START}
                  min={0}
                  max={2}
                  step={0.05}
                  onChange={(v) => setSampling({ temperature: v })}
                />
              )}
            </UiField>
            <UiField label="Top P">
              {() => (
                <OptionalSlider
                  label="Top P"
                  value={sampling.top_p}
                  start={TOP_P_START}
                  min={0}
                  max={1}
                  step={0.01}
                  onChange={(v) => setSampling({ top_p: v })}
                />
              )}
            </UiField>
          </>
        ) : null}
      </div>

      <Status message={saved} tone="success" />
    </Modal>
  );
}
