import { useEffect, useState } from 'react';
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
      </Section>

      <div className="settings-version">Version {version.data?.version ?? '…'}</div>
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
