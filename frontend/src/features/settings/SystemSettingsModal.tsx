import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Modal } from '../../components/ui/Modal';
import { ConfirmDialog } from '../../components/ui/ConfirmDialog';
import { Button } from '../../components/ui/Button';
import { SegmentedControl } from '../../components/ui/SegmentedControl';
import { showToast } from '../../components/ui/toast-store';
import { settingsApi, preferencesApi, settingsKeys, type CodeRunnerSettings } from '../../api/settings';
import { useSettingsStore } from '../../state/settings-store';
import { useUiStore, type ThemeMode } from '../../state/ui-store';
import { useModalStore, type DialogName } from '../../state/modal-store';
import { Field, Input } from '../../components/ui/Field';
import { Section, Status } from './forms';
import { Toggle } from '../../components/ui/Toggle';
import { SETTINGS_STALE_MS } from '../../api/settings';
import { useIsAdmin } from '../../state/user-store';
import { chatsApi, queryKeys } from '../../api/chats';
import { useStreamStore } from '../../state/stream-store';
import { stopIfStreaming } from '../chat/send-turn';
import { discardTemporaryChat } from '../chat/temporary-chat';
import { GitSettingsSection } from './GitSettingsSection';
import { ChatDefaultsSection } from './ChatDefaultsSection';

const THEMES: Array<[ThemeMode, string]> = [['light', 'Light'], ['dark', 'Dark'], ['system', 'System']];

/** System Settings: appearance, code runner limits, shortcuts to management dialogs, reset, version. */
export function SystemSettingsModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const queryClient = useQueryClient();
  const themeMode = useUiStore((s) => s.themeMode);
  const setTheme = useUiStore((s) => s.setThemeMode);
  const showDialog = useModalStore((s) => s.show);
  const isAdmin = useIsAdmin();
  const vision = useSettingsStore((s) => s.visionEnabled);
  const setVision = useSettingsStore((s) => s.setVisionEnabled);
  const system = useQuery({ queryKey: settingsKeys.system, queryFn: settingsApi.getSystem, enabled: open && isAdmin, staleTime: SETTINGS_STALE_MS });
  const version = useQuery({ queryKey: settingsKeys.version, queryFn: settingsApi.version, enabled: open, staleTime: SETTINGS_STALE_MS });
  const [runner, setRunner] = useState<CodeRunnerSettings | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [confirmReset, setConfirmReset] = useState(false);
  const [confirmClear, setConfirmClear] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    if (system.data && !runner) {
      setRunner({
        code_runner_timeout: system.data.code_runner_timeout,
        code_runner_memory_limit: system.data.code_runner_memory_limit,
        code_runner_cpu_limit: system.data.code_runner_cpu_limit,
        code_runner_max_output_size: system.data.code_runner_max_output_size,
      });
    }
  }, [system.data, runner]);

  const saveRunner = useMutation({
    mutationFn: (body: CodeRunnerSettings) => settingsApi.saveCodeRunner(body),
    onSuccess: () => {
      setStatus('Saved');
      void queryClient.invalidateQueries({ queryKey: settingsKeys.system });
    },
    onError: (e) => setStatus(e instanceof Error ? e.message : 'Save failed'),
  });

  /** Deletes every chat of the caller, then shows an empty home page. */
  async function deleteAllChats() {
    try {
      // Every turn that is generating is stopped first (the server's delete does not stop it): the ones
      // the chat list reports as running, which includes turns started in another tab, and this tab's own.
      const running = async () => (await chatsApi.list()).filter((c) => c.is_running).map((c) => c.id);
      const ids = new Set(await running());
      const own = useStreamStore.getState().chatId;
      if (own) ids.add(own);
      await Promise.all([...ids].map((id) => stopIfStreaming(id, true)));
      // A stop the server refused is only toasted by the stop itself: do not delete under a live turn.
      if ((await running()).length > 0) throw new Error('A chat is still generating. Try again once it has stopped.');
      await chatsApi.bulkDelete();
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Could not delete the chats', 'error');
      return;
    }
    // The chats are gone from here on; a failure below only leaves the screen to be refreshed.
    try {
      await discardTemporaryChat(queryClient);
      queryClient.removeQueries({ queryKey: ['chat'] });
      await queryClient.invalidateQueries({ queryKey: queryKeys.chats });
      await queryClient.invalidateQueries({ queryKey: queryKeys.workspaces });
    } catch {
      showToast('The chats were deleted, but the lists could not be refreshed. Reload the page.', 'error');
    }
    showToast('All chats deleted', 'success');
    onClose();
    navigate('/', { replace: true });
  }

  const reset = useMutation({
    mutationFn: () => preferencesApi.reset(),
    onSuccess: () => {
      showToast('Preferences reset', 'success');
      void queryClient.invalidateQueries({ queryKey: settingsKeys.preferences });
    },
  });

  const userLinks: Array<[DialogName, string]> = [
    ['preferences', 'Memory & preferences'],
    ['skills', 'Skills'],
    ['personas', 'Personas'],
  ];
  // Agent, model and browser settings are process-wide: the server refuses them for anyone but the admin.
  const adminLinks: Array<[DialogName, string]> = [
    ['agent-config', 'Agent configuration'],
    ['models', 'Model manager'],
    ['stealth', 'Browser stealth'],
  ];
  const links = isAdmin ? [...userLinks, ...adminLinks] : userLinks;

  return (
    <Modal open={open} onClose={onClose} title="System Settings" maxWidth={680}>
      <Section title="Appearance">
        <SegmentedControl
          label="Theme"
          value={themeMode}
          options={THEMES.map(([value, label]) => ({ value, label }))}
          onChange={(value) => setTheme(value as ThemeMode)}
        />
      </Section>

      <Section title="Capabilities">
        <Toggle
          checked={vision}
          onChange={setVision}
          label="Vision input"
          description="Send attached images to the model so it can read them."
        />
      </Section>

      <ChatDefaultsSection />

      {isAdmin ? (
        <Section title="Code runner">
          {runner ? (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                setStatus(null);
                saveRunner.mutate(runner);
              }}
            >
              <Field label="Timeout (seconds)">
                {(c) => (
                  <Input
                    {...c}
                    type="number"
                    min={1}
                    max={system.data?.code_runner_max_timeout}
                    value={runner.code_runner_timeout}
                    onChange={(e) => setRunner({ ...runner, code_runner_timeout: Number(e.target.value) })}
                  />
                )}
              </Field>
              <Field label="Memory limit" hint="For example 512M or 1G">
                {(c) => (
                  <Input
                    {...c}
                    value={runner.code_runner_memory_limit}
                    onChange={(e) => setRunner({ ...runner, code_runner_memory_limit: e.target.value })}
                  />
                )}
              </Field>
              <Field label="CPU limit (cores)">
                {(c) => (
                  <Input
                    {...c}
                    value={runner.code_runner_cpu_limit}
                    onChange={(e) => setRunner({ ...runner, code_runner_cpu_limit: e.target.value })}
                  />
                )}
              </Field>
              <Field label="Max output (bytes)">
                {(c) => (
                  <Input
                    {...c}
                    type="number"
                    min={1024}
                    value={runner.code_runner_max_output_size}
                    onChange={(e) => setRunner({ ...runner, code_runner_max_output_size: Number(e.target.value) })}
                  />
                )}
              </Field>
              <Button variant="primary" type="submit" disabled={saveRunner.isPending}>
                Save code runner settings
              </Button>
              <Status message={status} tone={status === 'Saved' ? 'success' : 'error'} />
            </form>
          ) : (
            <div className="settings-loading">Loading…</div>
          )}
        </Section>
      ) : null}

      {isAdmin && system.data ? <GitSettingsSection system={system.data} /> : null}

      <Section title="Manage">
        <div className="settings-links">
          {links.map(([name, label]) => (
            <Button key={name} variant="secondary" onClick={() => showDialog(name)}>{label}</Button>
          ))}
        </div>
      </Section>

      <Section title="Danger zone">
        <Button variant="danger" onClick={() => setConfirmReset(true)}>
          Reset preferences
        </Button>
        <Button variant="danger" onClick={() => setConfirmClear(true)}>
          Delete all chats
        </Button>
      </Section>

      <div className="settings-version">Version {version.data?.version ?? '…'}</div>
      <ConfirmDialog
        open={confirmClear}
        title="Delete all chats"
        message="Delete every chat, with its messages and files? This cannot be undone."
        confirmLabel="Delete all"
        danger
        onCancel={() => setConfirmClear(false)}
        onConfirm={() => {
          setConfirmClear(false);
          void deleteAllChats();
        }}
      />
      <ConfirmDialog
        open={confirmReset}
        title="Reset preferences"
        message="Reset all saved preferences to their defaults? This cannot be undone."
        confirmLabel="Reset"
        danger
        onCancel={() => setConfirmReset(false)}
        onConfirm={() => {
          setConfirmReset(false);
          reset.mutate();
        }}
      />
    </Modal>
  );
}
