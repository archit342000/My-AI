import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { chatsApi, queryKeys } from '../../../api/chats';
import {
  settingsApi,
  settingsKeys,
  SETTINGS_STALE_MS,
  type CodeRunnerSettings,
} from '../../../api/settings';
import { Button } from '../../../components/ui/Button';
import { ConfirmDialog } from '../../../components/ui/ConfirmDialog';
import { Field, Input } from '../../../components/ui/Field';
import { SegmentedControl } from '../../../components/ui/SegmentedControl';
import { Toggle } from '../../../components/ui/Toggle';
import { showToast } from '../../../components/ui/toast-store';
import { markSaved, trackSave } from '../../../lib/save-light';
import { useSettingsStore } from '../../../state/settings-store';
import { useStreamStore } from '../../../state/stream-store';
import { useUiStore, type GlassMode, type ThemeMode } from '../../../state/ui-store';
import { useIsAdmin, useUserStore } from '../../../state/user-store';
import { stopIfStreaming } from '../../chat/send-turn';
import { discardTemporaryChat } from '../../chat/temporary-chat';
import { SettingRow, SettingsSection, SubHead } from '../forms';

const THEMES: Array<{ value: ThemeMode; label: string }> = [
  { value: 'light', label: 'Light' },
  { value: 'dark', label: 'Dark' },
  { value: 'system', label: 'System' },
];
const PANELS: Array<{ value: GlassMode; label: string }> = [
  { value: 'auto', label: 'Auto' },
  { value: 'frosted', label: 'Frosted' },
  { value: 'solid', label: 'Solid' },
];

type RunnerField = keyof CodeRunnerSettings;
type RunnerDraft = Record<RunnerField, string>;

const toDraft = (s: CodeRunnerSettings): RunnerDraft => ({
  code_runner_timeout: String(s.code_runner_timeout),
  code_runner_memory_limit: String(s.code_runner_memory_limit),
  code_runner_cpu_limit: String(s.code_runner_cpu_limit),
  code_runner_max_output_size: String(s.code_runner_max_output_size),
});

/** What is wrong with each code-runner value, if anything. */
function runnerErrors(draft: RunnerDraft, maxTimeout: number | undefined): Partial<RunnerDraft> {
  const errors: Partial<RunnerDraft> = {};
  const timeout = Number(draft.code_runner_timeout);
  if (!Number.isFinite(timeout) || timeout < 1) errors.code_runner_timeout = 'At least 1 second.';
  else if (maxTimeout && timeout > maxTimeout)
    errors.code_runner_timeout = `At most ${maxTimeout} seconds.`;
  if (!draft.code_runner_memory_limit.trim())
    errors.code_runner_memory_limit = 'Give a size, for example 512M.';
  if (!draft.code_runner_cpu_limit.trim()) errors.code_runner_cpu_limit = 'Give a number of cores.';
  const output = Number(draft.code_runner_max_output_size);
  if (!Number.isFinite(output) || output < 1024)
    errors.code_runner_max_output_size = 'At least 1024 bytes.';
  return errors;
}

/** The code runner's limits (admin). A value is kept when its box is left or Enter is pressed. */
function CodeRunner() {
  const queryClient = useQueryClient();
  const system = useQuery({
    queryKey: settingsKeys.system,
    queryFn: settingsApi.getSystem,
    staleTime: SETTINGS_STALE_MS,
  });
  const [draft, setDraft] = useState<RunnerDraft | null>(null);
  const saved = useRef<RunnerDraft | null>(null);
  useEffect(() => {
    if (!system.data) return;
    const next = toDraft(system.data);
    // Follow the server, but never over something being typed.
    setDraft((current) =>
      current === null || JSON.stringify(current) === JSON.stringify(saved.current)
        ? next
        : current,
    );
    saved.current = next;
  }, [system.data]);

  if (!draft) {
    return (
      <p className="ui-hint crud-none" role={system.isError ? 'alert' : 'status'}>
        {system.isError ? 'The code runner settings could not be loaded.' : 'Loading'}
      </p>
    );
  }
  const errors = runnerErrors(draft, system.data?.code_runner_max_timeout);

  async function commit() {
    if (!draft || Object.keys(errors).length > 0) return;
    if (JSON.stringify(draft) === JSON.stringify(saved.current)) return;
    const sent = draft;
    try {
      await trackSave(
        settingsApi.saveCodeRunner({
          code_runner_timeout: Number(sent.code_runner_timeout),
          code_runner_memory_limit: sent.code_runner_memory_limit.trim(),
          code_runner_cpu_limit: sent.code_runner_cpu_limit.trim(),
          code_runner_max_output_size: Number(sent.code_runner_max_output_size),
        }),
      );
      saved.current = sent;
      void queryClient.invalidateQueries({ queryKey: settingsKeys.system });
    } catch (err) {
      showToast(
        err instanceof Error
          ? err.message
          : 'The code runner settings could not be saved. Try again.',
        'error',
      );
    }
  }

  const box = (
    field: RunnerField,
    label: string,
    extra: { type?: string; hint?: string; min?: number } = {},
  ) => (
    <Field label={label} hint={extra.hint} error={errors[field] ?? null}>
      {(c) => (
        <Input
          {...c}
          type={extra.type ?? 'text'}
          min={extra.min}
          value={draft[field]}
          onChange={(e) => setDraft({ ...draft, [field]: e.target.value })}
          onBlur={() => void commit()}
          onKeyDown={(e) => e.key === 'Enter' && void commit()}
        />
      )}
    </Field>
  );

  return (
    <div className="field-grid field-grid--two">
      {box('code_runner_timeout', 'Timeout (seconds)', { type: 'number', min: 1 })}
      {box('code_runner_memory_limit', 'Memory limit', { hint: 'For example 512M or 1G' })}
      {box('code_runner_cpu_limit', 'Processor limit (cores)')}
      {box('code_runner_max_output_size', 'Longest output (bytes)', { type: 'number', min: 1024 })}
    </div>
  );
}

/** System: how the app looks, what it may do, the code runner's limits, and deleting every chat. */
export function SystemSection() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const isAdmin = useIsAdmin();
  const user = useUserStore((s) => s.user);
  const themeMode = useUiStore((s) => s.themeMode);
  const glassMode = useUiStore((s) => s.glassMode);
  const vision = useSettingsStore((s) => s.visionEnabled);
  const version = useQuery({
    queryKey: settingsKeys.version,
    queryFn: settingsApi.version,
    staleTime: SETTINGS_STALE_MS,
  });
  const [confirmClear, setConfirmClear] = useState(false);

  /** Deletes every chat of the caller, then shows an empty home page. */
  async function deleteAllChats() {
    try {
      // Every turn that is generating is stopped first (the server's delete does not stop it): the ones
      // the chat list reports as running, which includes turns started in another tab, and this tab's own.
      const running = async () =>
        (await chatsApi.list()).filter((c) => c.is_running).map((c) => c.id);
      const ids = new Set(await running());
      const own = useStreamStore.getState().chatId;
      if (own) ids.add(own);
      await Promise.all([...ids].map((id) => stopIfStreaming(id, true)));
      // A stop the server refused is only toasted by the stop itself: do not delete under a live turn.
      if ((await running()).length > 0)
        throw new Error('A chat is still being answered. Try again once it has stopped.');
      await chatsApi.bulkDelete();
    } catch (err) {
      showToast(
        err instanceof Error ? err.message : 'The chats could not be deleted. Try again.',
        'error',
      );
      return;
    }
    // The chats are gone from here on; a failure below only leaves the screen to be refreshed.
    try {
      await discardTemporaryChat(queryClient);
      queryClient.removeQueries({ queryKey: ['chat'] });
      await queryClient.invalidateQueries({ queryKey: queryKeys.chats });
      await queryClient.invalidateQueries({ queryKey: queryKeys.workspaces });
    } catch {
      showToast(
        'The chats were deleted, but the lists could not be refreshed. Reload the page.',
        'error',
      );
    }
    showToast('All chats deleted', 'success');
    // Home, without the settings page on top.
    navigate('/', { replace: true });
  }

  return (
    <SettingsSection id="system" title="System">
      <SubHead>Appearance</SubHead>
      <SettingRow
        label="Theme"
        hint="System follows your device, light by day and dark by night."
        wide
      >
        {() => (
          <SegmentedControl
            label="Theme"
            value={themeMode}
            options={THEMES}
            onChange={(value) => {
              useUiStore.getState().setThemeMode(value as ThemeMode);
              markSaved();
            }}
          />
        )}
      </SettingRow>
      <SettingRow
        label="Panels"
        hint="Frosted panels blur what is behind them. Solid is lighter work for an older device. Auto picks for this one."
        wide
      >
        {() => (
          <SegmentedControl
            label="Panels"
            value={glassMode}
            options={PANELS}
            onChange={(value) => {
              useUiStore.getState().setGlassMode(value as GlassMode);
              markSaved();
            }}
          />
        )}
      </SettingRow>

      <SubHead>Capabilities</SubHead>
      <div className="set-row">
        <Toggle
          checked={vision}
          onChange={(on) => {
            useSettingsStore.getState().setVisionEnabled(on);
            markSaved();
          }}
          label="Vision input"
          description="Lets you attach pictures for the model to look at."
        />
      </div>

      {isAdmin ? (
        <>
          <SubHead>Code runner</SubHead>
          <CodeRunner />
        </>
      ) : null}

      <SubHead danger>Danger zone</SubHead>
      <div className="set-row">
        <div className="set-row__text">
          <div className="set-row__label">Delete all chats</div>
          <div className="ui-hint">
            Every chat, with its messages and files. This cannot be undone.
          </div>
        </div>
        <Button variant="danger" onClick={() => setConfirmClear(true)}>
          Delete all
        </Button>
      </div>

      <p className="dat keep set-about">
        Version {version.data?.version ?? '…'}
        {user ? ` · Signed in as ${user.email} (${user.role})` : ''}
      </p>
      <ConfirmDialog
        open={confirmClear}
        title="Delete all chats?"
        message="Every chat will be deleted, with its messages and files. This cannot be undone."
        confirmLabel="Delete all chats"
        danger
        onCancel={() => setConfirmClear(false)}
        onConfirm={() => {
          setConfirmClear(false);
          void deleteAllChats();
        }}
      />
    </SettingsSection>
  );
}
