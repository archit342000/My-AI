import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useMatch } from 'react-router';
import { modelsApi, personasApi, settingsKeys, SETTINGS_STALE_MS } from '../../../api/settings';
import { SegmentedControl } from '../../../components/ui/SegmentedControl';
import { Select } from '../../../components/ui/Select';
import { Slider } from '../../../components/ui/Slider';
import { Toggle } from '../../../components/ui/Toggle';
import { thinkingProfileLabel } from '../../../lib/labels';
import { modelSelectOptions } from '../../../lib/model-options';
import { markSaved } from '../../../lib/save-light';
import { useSettingsStore } from '../../../state/settings-store';
import { useChatDetail } from '../../chat/useChatQueries';
import { SettingRow, SettingsSection, SubHead } from '../forms';

const PROFILES = ['general', 'precision', 'none'];
const PROFILE_OPTIONS = PROFILES.map((p) => ({ value: p, label: thinkingProfileLabel(p) }));

/**
 * A sampling value the model can decide itself: an empty box means "model default" (the value is
 * then left out of what is sent), a number sets it.
 */
function OptionalNumber({
  id,
  labelId,
  hintId,
  value,
  min,
  max,
  step,
  onChange,
}: {
  id: string;
  labelId: string;
  hintId: string | undefined;
  value: number | undefined;
  min: number;
  max: number;
  step: number;
  onChange: (value: number | undefined) => void;
}) {
  // While the box is focused it shows what is being typed ("0." on the way to "0.4").
  const [typed, setTyped] = useState<string | null>(null);
  return (
    <input
      id={id}
      className="ui-input set-num"
      type="number"
      inputMode="decimal"
      aria-labelledby={labelId}
      aria-describedby={hintId}
      placeholder="model default"
      min={min}
      max={max}
      step={step}
      value={typed ?? (value === undefined ? '' : String(value))}
      onChange={(e) => {
        const text = e.target.value;
        setTyped(text);
        if (text.trim() === '') return onChange(undefined);
        const n = Number(text);
        if (Number.isFinite(n)) onChange(Math.min(max, Math.max(min, n)));
      }}
      onBlur={() => setTyped(null)}
    />
  );
}

/**
 * Chat: the model, how it thinks, the persona and the sampling values for the next message. Opened
 * from a chat, these are that chat's own values (the section says so) and what new chats start with
 * is listed apart; anywhere else they are the values every new chat starts with.
 */
export function ChatSection() {
  const model = useSettingsStore((s) => s.model);
  const userPreferences = useSettingsStore((s) => s.userPreferences);
  const sampling = useSettingsStore((s) => s.sampling);
  const personaId = useSettingsStore((s) => s.personaId);
  const chatScoped = useSettingsStore((s) => s.chatScoped);
  const defaults = useSettingsStore((s) => s.defaults);
  const store = useSettingsStore.getState;
  const models = useQuery({
    queryKey: settingsKeys.models,
    queryFn: modelsApi.list,
    staleTime: SETTINGS_STALE_MS,
  });
  const personas = useQuery({
    queryKey: settingsKeys.personas,
    queryFn: personasApi.list,
    staleTime: SETTINGS_STALE_MS,
  });
  // The chat beneath the settings page, when there is one: its title says whose values these are.
  const chatId = useMatch('/chat/:chatId')?.params.chatId;
  const chat = useChatDetail(chatId);
  const chatTitle = chat.data?.title || 'this chat';

  /** Runs a setter and lights Saved: these values are kept the moment they change. */
  const apply = (change: () => void) => {
    change();
    markSaved();
  };

  return (
    <SettingsSection
      id="chat"
      title="Chat"
      lead={
        chatScoped
          ? `These apply to "${chatTitle}" from its next message. What new chats start with is further down.`
          : 'Used for the next message, and what every new chat starts with.'
      }
    >
      <SettingRow label="Model" hint="Answers the next message." wide>
        {({ id }) => (
          <Select
            id={id}
            aria-label="Model"
            placeholder="Choose a model"
            searchable
            searchPlaceholder="Search models"
            value={model ?? ''}
            options={modelSelectOptions(models.data ?? [])}
            onChange={(next) => apply(() => store().setModel(next, next))}
          />
        )}
      </SettingRow>
      <SettingRow
        label="Thinking profile"
        hint="How much the model reasons before it answers."
        wide
      >
        {() => (
          <SegmentedControl
            label="Thinking profile"
            value={sampling.thinking_profile}
            options={PROFILE_OPTIONS}
            onChange={(v) => apply(() => store().setSampling({ thinking_profile: v }))}
          />
        )}
      </SettingRow>
      <SettingRow label="Persona" hint="Its standing instructions apply to new messages." wide>
        {({ id }) => (
          <Select
            id={id}
            aria-label="Persona"
            value={personaId ?? ''}
            options={[
              { value: '', label: 'None' },
              ...(personas.data ?? []).map((p) => ({ value: p.id, label: p.name })),
            ]}
            onChange={(v) => apply(() => store().setPersona(v || null))}
          />
        )}
      </SettingRow>
      <div className="set-row">
        <Toggle
          checked={userPreferences}
          onChange={(v) => apply(() => store().setUserPreferences(v))}
          label="Use what it remembers about you"
          description="Answers draw on your saved memory and preferences."
        />
      </div>

      <SubHead>Sampling</SubHead>
      <SettingRow
        label="Longest answer"
        hint="In tokens, roughly three-quarters of a word each."
        wide
      >
        {() => (
          <Slider
            label="Longest answer"
            value={sampling.max_tokens}
            min={256}
            max={32768}
            step={256}
            decimals={0}
            onChange={(v) => apply(() => store().setSampling({ max_tokens: v }))}
          />
        )}
      </SettingRow>
      <SettingRow label="Thinking budget" hint="The most tokens it may spend reasoning." wide>
        {() => (
          <Slider
            label="Thinking budget"
            value={sampling.thinking_budget_tokens}
            min={0}
            max={8000}
            step={100}
            decimals={0}
            onChange={(v) => apply(() => store().setSampling({ thinking_budget_tokens: v }))}
          />
        )}
      </SettingRow>
      <SettingRow label="Temperature" hint="Lower is steadier, higher is more varied.">
        {(ids) => (
          <OptionalNumber
            {...ids}
            value={sampling.temperature}
            min={0}
            max={2}
            step={0.05}
            onChange={(v) => apply(() => store().setSampling({ temperature: v }))}
          />
        )}
      </SettingRow>
      <SettingRow label="Top P" hint="Leave empty to use the model's own setting.">
        {(ids) => (
          <OptionalNumber
            {...ids}
            value={sampling.top_p}
            min={0}
            max={1}
            step={0.05}
            onChange={(v) => apply(() => store().setSampling({ top_p: v }))}
          />
        )}
      </SettingRow>

      {chatScoped ? (
        <>
          <SubHead>New chats start with</SubHead>
          <SettingRow label="Thinking profile" wide>
            {() => (
              <SegmentedControl
                label="Thinking profile for new chats"
                value={defaults.sampling.thinking_profile}
                options={PROFILE_OPTIONS}
                onChange={(v) => apply(() => store().setDefaults({ thinking_profile: v }))}
              />
            )}
          </SettingRow>
          <div className="set-row">
            <Toggle
              checked={defaults.userPreferences}
              onChange={(on) => apply(() => store().setDefaults({ userPreferences: on }))}
              label="Use what it remembers about you"
              description="New chats draw on your saved memory and preferences."
            />
          </div>
          <SettingRow label="Longest answer" wide>
            {() => (
              <Slider
                label="Longest answer in new chats"
                value={defaults.sampling.max_tokens}
                min={256}
                max={32768}
                step={256}
                decimals={0}
                onChange={(v) => apply(() => store().setDefaults({ max_tokens: v }))}
              />
            )}
          </SettingRow>
          <SettingRow label="Thinking budget" wide>
            {() => (
              <Slider
                label="Thinking budget in new chats"
                value={defaults.sampling.thinking_budget_tokens}
                min={0}
                max={8000}
                step={100}
                decimals={0}
                onChange={(v) => apply(() => store().setDefaults({ thinking_budget_tokens: v }))}
              />
            )}
          </SettingRow>
        </>
      ) : null}
    </SettingsSection>
  );
}
