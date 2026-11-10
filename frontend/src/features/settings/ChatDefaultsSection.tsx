import type { ThinkingProfile } from '../../api/settings';
import { Select } from '../../components/ui/Select';
import { Slider } from '../../components/ui/Slider';
import { Toggle } from '../../components/ui/Toggle';
import { Field } from '../../components/ui/Field';
import { thinkingProfileLabel } from '../../lib/labels';
import { useSettingsStore } from '../../state/settings-store';
import { Section } from './forms';

const PROFILES: ThinkingProfile[] = ['general', 'precision', 'none'];

/** What a new chat starts with (thinking profile, user preferences, max tokens, thinking budget). */
export function ChatDefaultsSection() {
  const defaults = useSettingsStore((s) => s.defaults);
  const setDefaults = useSettingsStore((s) => s.setDefaults);
  return (
    <Section title="New chat defaults">
      <Field label="Thinking profile">
        {(c) => (
          <Select
            id={c.id}
            aria-label="Default thinking profile"
            value={defaults.sampling.thinking_profile}
            options={PROFILES.map((p) => ({ value: p, label: thinkingProfileLabel(p) }))}
            onChange={(v) => setDefaults({ thinking_profile: v })}
          />
        )}
      </Field>
      <Toggle
        checked={defaults.userPreferences}
        onChange={(on) => setDefaults({ userPreferences: on })}
        label="User preferences"
        description="Personalise responses in new chats using your profile and learned preferences."
      />
      <Field label="Max tokens">
        {() => (
          <Slider
            label="Max tokens"
            value={defaults.sampling.max_tokens}
            min={256}
            max={32768}
            step={256}
            decimals={0}
            onChange={(v) => setDefaults({ max_tokens: v })}
          />
        )}
      </Field>
      <Field label="Thinking budget">
        {() => (
          <Slider
            label="Thinking budget"
            value={defaults.sampling.thinking_budget_tokens}
            min={0}
            max={8000}
            step={100}
            decimals={0}
            onChange={(v) => setDefaults({ thinking_budget_tokens: v })}
          />
        )}
      </Field>
    </Section>
  );
}
