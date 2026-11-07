import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Modal } from '../../components/ui/Modal';
import { modelsApi, personasApi, settingsKeys } from '../../api/settings';
import { useSettingsStore } from '../../state/settings-store';
import { Field, Section, Status, inputStyle } from './forms';

type Tab = 'general' | 'persona' | 'parameters';

/** Chat Settings: model, thinking, sampling parameters and persona (legacy tabs). */
export function ChatSettingsModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [tab, setTab] = useState<Tab>('general');
  const settings = useSettingsStore();
  const models = useQuery({ queryKey: settingsKeys.models, queryFn: modelsApi.list, enabled: open });
  const personas = useQuery({ queryKey: settingsKeys.personas, queryFn: personasApi.list, enabled: open });
  const [saved, setSaved] = useState<string | null>(null);

  const tabs: Array<[Tab, string]> = [['general', 'General'], ['persona', 'Persona'], ['parameters', 'Parameters']];

  return (
    <Modal open={open} onClose={onClose} title="Chat Settings" maxWidth={640}>
      <div role="tablist" style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        {tabs.map(([key, label]) => (
          <button key={key} role="tab" aria-selected={tab === key} type="button" className={tab === key ? 'btn-primary' : 'btn-ghost'} onClick={() => setTab(key)}>
            {label}
          </button>
        ))}
      </div>

      {tab === 'general' ? (
        <Section title="Model">
          <Field label="Model" hint="Used for the next message.">
            <select
              style={inputStyle}
              value={settings.model ?? ''}
              onChange={(e) => {
                const m = models.data?.find((x) => x.id === e.target.value);
                settings.setModel(e.target.value, m?.id ?? e.target.value);
                setSaved('Model updated');
              }}
            >
              {!settings.model ? <option value="">Select a model</option> : null}
              {(models.data ?? []).map((m) => (
                <option key={m.id} value={m.id}>{m.id}</option>
              ))}
            </select>
          </Field>
          <Field label="Thinking profile">
            <select style={inputStyle} value={settings.sampling.thinking_profile} onChange={(e) => settings.setSampling({ thinking_profile: e.target.value })}>
              <option value="general">General</option>
              <option value="precision">Precision</option>
              <option value="none">None</option>
            </select>
          </Field>
        </Section>
      ) : null}

      {tab === 'persona' ? (
        <Section title="Persona">
          <Field label="Active persona" hint="Applies its instructions to new messages.">
            <select style={inputStyle} value={settings.personaId ?? ''} onChange={(e) => settings.setPersona(e.target.value || null)}>
              <option value="">None</option>
              {(personas.data ?? []).map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </Field>
        </Section>
      ) : null}

      {tab === 'parameters' ? (
        <Section title="Sampling">
          <Field label={`Max tokens: ${settings.sampling.max_tokens}`}>
            <input type="range" min={256} max={32768} step={256} value={settings.sampling.max_tokens} onChange={(e) => settings.setSampling({ max_tokens: Number(e.target.value) })} />
          </Field>
          <Field label={`Thinking budget: ${settings.sampling.thinking_budget_tokens}`}>
            <input type="range" min={0} max={8000} step={100} value={settings.sampling.thinking_budget_tokens} onChange={(e) => settings.setSampling({ thinking_budget_tokens: Number(e.target.value) })} />
          </Field>
          <Field label={`Temperature: ${settings.sampling.temperature ?? 'model default'}`}>
            <input type="number" step={0.05} min={0} max={2} style={inputStyle} value={settings.sampling.temperature ?? ''} placeholder="model default" onChange={(e) => settings.setSampling({ temperature: e.target.value === '' ? undefined : Number(e.target.value) })} />
          </Field>
          <Field label={`Top P: ${settings.sampling.top_p ?? 'model default'}`}>
            <input type="number" step={0.05} min={0} max={1} style={inputStyle} value={settings.sampling.top_p ?? ''} placeholder="model default" onChange={(e) => settings.setSampling({ top_p: e.target.value === '' ? undefined : Number(e.target.value) })} />
          </Field>
        </Section>
      ) : null}

      <Status message={saved} tone="success" />
    </Modal>
  );
}
