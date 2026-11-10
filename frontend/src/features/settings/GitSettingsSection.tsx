import { useEffect, useRef, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { settingsApi, settingsKeys, type SystemSettings } from '../../api/settings';
import { Button } from '../../components/ui/Button';
import { Field, Input } from '../../components/ui/Field';
import { showToast } from '../../components/ui/toast-store';
import { Checkbox } from '../../components/ui/Checkbox';
import { trackSave } from '../../lib/save-light';
import { Status } from './forms';

/**
 * Git agent settings (admin): a write-only GitHub token and the git commands the agent may run.
 * The server never returns the token, so the field only ever shows whether one is configured.
 */
export function GitSettings({ system }: { system: SystemSettings }) {
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
    mutationFn: (commands: string[]) => trackSave(settingsApi.saveGitAllowedCommands(commands)),
    onSuccess: (_data, commands) => {
      confirmed.current = commands;
      return refresh();
    },
    onError: (err) => {
      setAllowed(confirmed.current);
      showToast(
        err instanceof Error ? err.message : 'The allowed commands could not be saved. Try again.',
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
      await trackSave(settingsApi.saveGitToken(value));
      setToken('');
      setTokenStatus({ tone: 'success', message: 'Token saved' });
      await refresh();
    } catch (err) {
      setTokenStatus({
        tone: 'error',
        message: err instanceof Error ? err.message : 'The token could not be saved. Try again.',
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
    <>
      <form
        className="set-token"
        onSubmit={(e) => {
          e.preventDefault();
          if (token.trim()) void saveToken(token.trim());
        }}
      >
        <Field
          label="GitHub token"
          hint={
            system.github_pat_configured
              ? 'One is set. Enter a new token to replace it; it is never shown again.'
              : 'None set. It is sent once and never shown again.'
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
        <Button variant="secondary" type="submit" disabled={!token.trim()} loading={saving}>
          Save token
        </Button>
        <Status message={tokenStatus?.message ?? null} tone={tokenStatus?.tone ?? 'error'} />
      </form>
      <fieldset className="settings-checks">
        <legend className="set-row__label settings-checks__legend">Allowed git commands</legend>
        <div className="settings-checks__grid">
          {known.map((command) => (
            <Checkbox
              key={command}
              checked={allowed.includes(command)}
              disabled={saveCommands.isPending}
              onChange={(on) => toggle(command, on)}
            >
              <span className="font-mono">{command}</span>
            </Checkbox>
          ))}
        </div>
      </fieldset>
    </>
  );
}
