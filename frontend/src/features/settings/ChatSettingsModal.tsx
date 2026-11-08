import { useState } from 'react';
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
  const settings = useSettingsStore();
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
  const [saved, setSaved] = useState<string | null>(null);

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
                  value={settings.model ?? ''}
                  options={modelSelectOptions(models.data ?? [])}
                  onChange={(id) => {
                    settings.setModel(id, id);
                    setSaved('Model updated');
                  }}
                />
              )}
            </UiField>
            <Toggle
              checked={settings.userPreferences}
              onChange={(v) => settings.setUserPreferences(v)}
              label="User preferences"
              description="Personalise responses using your profile and learned preferences."
            />
            <UiField label="Thinking profile">
              {(c) => (
                <Select
                  id={c.id}
                  aria-label="Thinking profile"
                  value={settings.sampling.thinking_profile}
                  options={['general', 'precision', 'none'].map((p) => ({ value: p, label: thinkingProfileLabel(p) }))}
                  onChange={(v) => settings.setSampling({ thinking_profile: v })}
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
                value={settings.personaId ?? ''}
                options={[{ value: '', label: 'None' }, ...(personas.data ?? []).map((p) => ({ value: p.id, label: p.name }))]}
                onChange={(v) => settings.setPersona(v || null)}
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
                  value={settings.sampling.max_tokens}
                  min={256}
                  max={32768}
                  step={256}
                  decimals={0}
                  onChange={(v) => settings.setSampling({ max_tokens: v })}
                />
              )}
            </UiField>
            <UiField label="Thinking budget">
              {() => (
                <Slider
                  label="Thinking budget"
                  value={settings.sampling.thinking_budget_tokens}
                  min={0}
                  max={8000}
                  step={100}
                  decimals={0}
                  onChange={(v) => settings.setSampling({ thinking_budget_tokens: v })}
                />
              )}
            </UiField>
            <UiField label="Temperature">
              {() => (
                <OptionalSlider
                  label="Temperature"
                  value={settings.sampling.temperature}
                  start={TEMPERATURE_START}
                  min={0}
                  max={2}
                  step={0.05}
                  onChange={(v) => settings.setSampling({ temperature: v })}
                />
              )}
            </UiField>
            <UiField label="Top P">
              {() => (
                <OptionalSlider
                  label="Top P"
                  value={settings.sampling.top_p}
                  start={TOP_P_START}
                  min={0}
                  max={1}
                  step={0.01}
                  onChange={(v) => settings.setSampling({ top_p: v })}
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
