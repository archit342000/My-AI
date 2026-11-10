import { useEffect, useRef, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { settingsApi, settingsKeys, type SystemSettings } from '../../api/settings';
import { Button } from '../../components/ui/Button';
import { Field, Input } from '../../components/ui/Field';
import { showToast } from '../../components/ui/toast-store';
import { Section, Status } from './forms';

/**
 * Git agent settings (admin): a write-only GitHub token and the git commands the agent may run.
 * The server never returns the token, so the field only ever shows whether one is configured.
 */
export function GitSettingsSection({ system }: { system: SystemSettings }) {
  const queryClient = useQueryClient();
  const refresh = () => queryClient.invalidateQueries({ queryKey: settingsKeys.system });
  const [token, setToken] = useState('');
  const [saving, setSaving] = useState(false);
  const [tokenStatus, setTokenStatus] = useState<{
    tone: 'success' | 'error';
    message: string;
  } | null>(null);
  const known = system.git_known_commands ?? [];
  const [allowed, setAllowed] = useState<string[]>(system.git_allowed_commands ?? []);
  // The last list the server confirmed: where the boxes go back to when a save fails.
  const confirmed = useRef<string[]>(system.git_allowed_commands ?? []);

  const saveCommands = useMutation({
    mutationFn: (commands: string[]) => settingsApi.saveGitAllowedCommands(commands),
    onSuccess: (_data, commands) => {
      confirmed.current = commands;
      return refresh();
    },
    onError: (err) => {
      setAllowed(confirmed.current);
      showToast(
        err instanceof Error ? err.message : 'Could not save the allowed commands',
        'error',
      );
    },
  });

  // Follow the server's list when it changes, but not over a save that is still in flight.
  useEffect(() => {
    if (saveCommands.isPending) return;
    confirmed.current = system.git_allowed_commands ?? [];
    setAllowed(confirmed.current);
  }, [system.git_allowed_commands, saveCommands.isPending]);

  /** Sent once and not kept: a plain call, so the token is not held in the mutation cache either. */
  async function saveToken(value: string) {
    setSaving(true);
    setTokenStatus(null);
    try {
      await settingsApi.saveGitToken(value);
      setToken('');
      setTokenStatus({ tone: 'success', message: 'Token saved' });
      await refresh();
    } catch (err) {
      setTokenStatus({
        tone: 'error',
        message: err instanceof Error ? err.message : 'Save failed',
      });
    } finally {
      setSaving(false);
    }
  }

  function toggle(command: string, on: boolean) {
    const next = on ? [...allowed, command] : allowed.filter((c) => c !== command);
    setAllowed(next);
    saveCommands.mutate(next);
  }

  return (
    <Section title="Git agent">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (token.trim()) void saveToken(token.trim());
        }}
      >
        <Field
          label="GitHub token"
          hint={
            system.github_pat_configured
              ? 'Configured. Enter a new token to replace it.'
              : 'Not configured.'
          }
        >
          {(c) => (
            <Input
              {...c}
              type="password"
              autoComplete="off"
              placeholder={system.github_pat_configured ? '••••••••' : 'ghp_…'}
              value={token}
              onChange={(e) => setToken(e.target.value)}
            />
          )}
        </Field>
        <Button variant="primary" type="submit" disabled={!token.trim() || saving}>
          Save token
        </Button>
        <Status message={tokenStatus?.message ?? null} tone={tokenStatus?.tone ?? 'error'} />
      </form>
      <fieldset className="settings-checks">
        <legend className="settings-checks__legend">Allowed git commands</legend>
        {known.map((command) => (
          <label key={command} className="settings-check">
            <input
              type="checkbox"
              checked={allowed.includes(command)}
              disabled={saveCommands.isPending}
              onChange={(e) => toggle(command, e.target.checked)}
            />
            <span className="font-mono">{command}</span>
          </label>
        ))}
      </fieldset>
    </Section>
  );
}
