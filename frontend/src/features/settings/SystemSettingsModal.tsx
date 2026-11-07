import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Modal } from '../../components/ui/Modal';
import { showToast } from '../../components/ui/toast-store';
import { settingsApi, preferencesApi, settingsKeys, type CodeRunnerSettings } from '../../api/settings';
import { useSettingsStore } from '../../state/settings-store';
import { useUiStore, type ThemeMode } from '../../state/ui-store';
import { useModalStore, type DialogName } from '../../state/modal-store';
import { Field, Section, Status, Toggle, inputStyle } from './forms';

const THEMES: Array<[ThemeMode, string]> = [['light', 'Light'], ['dark', 'Dark'], ['system', 'System']];

/** System Settings: appearance, code runner limits, shortcuts to management dialogs, reset, version. */
export function SystemSettingsModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const queryClient = useQueryClient();
  const themeMode = useUiStore((s) => s.themeMode);
  const setTheme = useUiStore((s) => s.setThemeMode);
  const showDialog = useModalStore((s) => s.show);
  const vision = useSettingsStore((s) => s.visionEnabled);
  const setVision = useSettingsStore((s) => s.setVisionEnabled);
  const system = useQuery({ queryKey: settingsKeys.system, queryFn: settingsApi.getSystem, enabled: open });
  const version = useQuery({ queryKey: settingsKeys.version, queryFn: settingsApi.version, enabled: open });
  const [runner, setRunner] = useState<CodeRunnerSettings | null>(null);
  const [status, setStatus] = useState<string | null>(null);

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
        <div role="radiogroup" aria-label="Theme" style={{ display: 'flex', gap: 8 }}>
          {THEMES.map(([mode, label]) => (
            <button key={mode} type="button" role="radio" aria-checked={themeMode === mode} className={themeMode === mode ? 'btn-primary' : 'btn-secondary'} onClick={() => setTheme(mode)}>
              {label}
            </button>
          ))}
        </div>
      </Section>

      <Section title="Capabilities">
        <Field label="Vision input">
          <Toggle checked={vision} onChange={setVision} label="Vision input" />
        </Field>
      </Section>

      <Section title="Code runner">
        {runner ? (
          <form onSubmit={(e) => { e.preventDefault(); setStatus(null); saveRunner.mutate(runner); }}>
            <Field label="Timeout (seconds)">
              <input type="number" min={1} style={inputStyle} value={runner.code_runner_timeout} onChange={(e) => setRunner({ ...runner, code_runner_timeout: Number(e.target.value) })} />
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
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {links.map(([name, label]) => (
            <button key={name} type="button" className="btn-secondary" onClick={() => showDialog(name)}>{label}</button>
          ))}
        </div>
      </Section>

      <Section title="Danger zone">
        <button type="button" className="btn-danger" onClick={() => { if (window.confirm('Reset all saved preferences? This cannot be undone.')) reset.mutate(); }}>
          Reset preferences
        </button>
      </Section>

      <div style={{ fontSize: '0.75rem', color: 'var(--content-muted)' }}>
        Version {version.data?.version ?? '…'}
      </div>
    </Modal>
  );
}
