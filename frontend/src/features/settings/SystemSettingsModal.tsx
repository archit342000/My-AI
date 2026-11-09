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
import { Field, Section, Status } from './forms';
import { inputStyle } from './form-styles';
import { Toggle } from '../../components/ui/Toggle';
import { SETTINGS_STALE_MS } from '../../api/settings';

const THEMES: Array<[ThemeMode, string]> = [['light', 'Light'], ['dark', 'Dark'], ['system', 'System']];

/** System Settings: appearance, code runner limits, shortcuts to management dialogs, reset, version. */
export function SystemSettingsModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const queryClient = useQueryClient();
  const themeMode = useUiStore((s) => s.themeMode);
  const setTheme = useUiStore((s) => s.setThemeMode);
  const showDialog = useModalStore((s) => s.show);
  const vision = useSettingsStore((s) => s.visionEnabled);
  const setVision = useSettingsStore((s) => s.setVisionEnabled);
  const system = useQuery({ queryKey: settingsKeys.system, queryFn: settingsApi.getSystem, enabled: open, staleTime: SETTINGS_STALE_MS });
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

  const links: Array<[DialogName, string]> = [
    ['preferences', 'Memory & preferences'],
    ['skills', 'Skills'],
    ['personas', 'Personas'],
    ['agent-config', 'Agent configuration'],
    ['models', 'Model manager'],
    ['stealth', 'Browser stealth'],
  ];

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

      <Section title="Code runner">
        {runner ? (
          <form onSubmit={(e) => { e.preventDefault(); setStatus(null); saveRunner.mutate(runner); }}>
            <Field label="Timeout (seconds)">
              <input type="number" min={1} max={system.data?.code_runner_max_timeout} style={inputStyle} value={runner.code_runner_timeout} onChange={(e) => setRunner({ ...runner, code_runner_timeout: Number(e.target.value) })} />
            </Field>
            <Field label="Memory limit" hint="For example 512M or 1G">
              <input style={inputStyle} value={runner.code_runner_memory_limit} onChange={(e) => setRunner({ ...runner, code_runner_memory_limit: e.target.value })} />
            </Field>
            <Field label="CPU limit (cores)">
              <input style={inputStyle} value={runner.code_runner_cpu_limit} onChange={(e) => setRunner({ ...runner, code_runner_cpu_limit: e.target.value })} />
            </Field>
            <Field label="Max output (bytes)">
              <input type="number" min={1024} style={inputStyle} value={runner.code_runner_max_output_size} onChange={(e) => setRunner({ ...runner, code_runner_max_output_size: Number(e.target.value) })} />
            </Field>
            <button type="submit" className="btn-primary" disabled={saveRunner.isPending}>Save code runner settings</button>
            <Status message={status} tone={status === 'Saved' ? 'success' : 'error'} />
          </form>
        ) : (
          <div style={{ color: 'var(--content-muted)' }}>Loading…</div>
        )}
      </Section>

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

      <div style={{ fontSize: '0.75rem', color: 'var(--content-muted)' }}>
        Version {version.data?.version ?? '…'}
      </div>
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
