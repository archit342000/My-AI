import type { Skill } from '../../api/settings';

export interface SlashCommand {
  /** Text inserted into the composer, including the leading slash. */
  name: string;
  description: string;
  kind: 'builtin' | 'skill';
}

/** Built-in slash commands, always listed first. */
export const SLASH_COMMANDS: readonly SlashCommand[] = [
  { name: '/help', description: 'Show available commands and skills', kind: 'builtin' },
  { name: '/skills', description: 'Manage custom skills', kind: 'builtin' },
];

/** Built-ins followed by one `/name` entry per user skill (skills whose name is usable as a command). */
export function slashCommandsFor(skills: readonly Skill[] | undefined): SlashCommand[] {
  const custom = (skills ?? [])
    .filter((s) => s.name.trim().length > 0)
    .map<SlashCommand>((s) => ({
      name: `/${s.name.trim().replace(/^\/+/, '')}`,
      description: s.description.trim() || 'Custom skill',
      kind: 'skill',
    }));
  const seen = new Set<string>();
  return [...SLASH_COMMANDS, ...custom].filter((c) => {
    if (seen.has(c.name)) return false;
    seen.add(c.name);
    return true;
  });
}

/**
 * Commands matching the text typed so far. Only while the text is a single `/word` (no spaces).
 * Prefix matches rank before substring matches.
 */
export function matchSlashCommands(
  commands: readonly SlashCommand[],
  text: string,
): SlashCommand[] {
  if (!text.startsWith('/') || /\s/.test(text)) return [];
  const query = text.toLowerCase();
  const prefix = commands.filter((c) => c.name.toLowerCase().startsWith(query));
  const contains = commands.filter(
    (c) =>
      !c.name.toLowerCase().startsWith(query) &&
      (c.name.toLowerCase().includes(query.slice(1)) ||
        c.description.toLowerCase().includes(query.slice(1))),
  );
  return [...prefix, ...contains];
}
