import { StatusLight } from '../../components/ui/StatusLight';
import { useSaveLight } from '../../lib/save-light';

/** The Saving / Saved light in the settings header. Nothing shows until something was changed. */
export function SavedLight() {
  const state = useSaveLight((s) => s.state);
  if (state === 'idle') return null;
  return (
    <StatusLight
      className="set-saved"
      label={state === 'saving' ? 'Saving' : state === 'error' ? 'Not saved' : 'Saved'}
      tone={state === 'saved' ? 'ok' : state === 'error' ? 'bad' : 'neutral'}
      busy={state === 'saving'}
    />
  );
}
