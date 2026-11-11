import { Chip } from '../../components/ui/Chip';
import { useSettingsStore } from '../../state/settings-store';
import { useIsAdmin } from '../../state/user-store';
import { availableModes } from './modes';

/** A chip in the message box for every tool that is switched on, so what the next message will use is visible. */
export function ActiveTools() {
  const modes = useSettingsStore((s) => s.modes);
  const setMode = useSettingsStore((s) => s.setMode);
  const isAdmin = useIsAdmin();
  const on = availableModes(isAdmin).filter((mode) => modes[mode.key]);
  if (on.length === 0) return null;
  return (
    <div className="composer-tools" role="group" aria-label="Tools that are on">
      {on.map((mode) => (
        <Chip
          key={mode.key}
          tint
          removeLabel={`Switch off ${mode.name}`}
          onRemove={() => setMode(mode.key, false)}
        >
          {mode.name}
        </Chip>
      ))}
    </div>
  );
}
