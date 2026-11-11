import { Window } from '../../components/ui/Window';
import type { SlashCommand } from './slash';

/** What `/help` shows: the built-in commands and the user's skills, each with its description. */
export function HelpDialog({
  open,
  onClose,
  commands,
}: {
  open: boolean;
  onClose: () => void;
  commands: readonly SlashCommand[];
}) {
  return (
    <Window open={open} onClose={onClose} title="Commands and skills" maxWidth={560}>
      <ul className="help-list">
        {commands.map((c) => (
          <li key={c.name} className="help-list__item">
            <span className="help-list__name font-mono">{c.name}</span>
            <span className="help-list__desc">{c.description}</span>
          </li>
        ))}
      </ul>
      <p className="help-list__note">
        Type a command in the message box and press Enter; a skill runs with its /name.
      </p>
    </Window>
  );
}
