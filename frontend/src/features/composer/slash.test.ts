import { describe, expect, it } from 'vitest';
import type { Skill } from '../../api/settings';
import { matchSlashCommands, slashCommandsFor, SLASH_COMMANDS } from './slash';

const skill = (name: string, description = ''): Skill => ({
  id: name,
  name,
  description,
  instructions: '',
});

describe('slashCommandsFor', () => {
  it('lists built-ins first, then one entry per skill with a slash prefix', () => {
    const commands = slashCommandsFor([skill('summarize', 'Summarise text'), skill('/review')]);
    expect(commands.map((c) => c.name)).toEqual([
      '/help',
      '/skills',
      '/summarize',
      '/review',
    ]);
    expect(commands[2]).toMatchObject({ kind: 'skill', description: 'Summarise text' });
    expect(commands[3]?.description).toBe('Custom skill');
  });

  it('returns only the built-ins while skills are not loaded', () => {
    expect(slashCommandsFor(undefined)).toHaveLength(SLASH_COMMANDS.length);
  });

  it('drops skills with an empty name and duplicate names', () => {
    const commands = slashCommandsFor([skill('  '), skill('help')]);
    expect(commands.map((c) => c.name)).toEqual(['/help', '/skills']);
  });
});

describe('matchSlashCommands', () => {
  const commands = slashCommandsFor([skill('summarize', 'Make it short'), skill('translate')]);

  it('returns nothing unless the text is a single slash word', () => {
    expect(matchSlashCommands(commands, 'hello')).toEqual([]);
    expect(matchSlashCommands(commands, '/help me')).toEqual([]);
  });

  it('shows everything for a bare slash', () => {
    expect(matchSlashCommands(commands, '/')).toHaveLength(commands.length);
  });

  it('filters by prefix and then by substring of name or description', () => {
    expect(matchSlashCommands(commands, '/sum').map((c) => c.name)).toEqual(['/summarize']);
    // Prefix matches come first; the description substring matches follow.
    expect(matchSlashCommands(commands, '/SK')[0]?.name).toBe('/skills');
    expect(matchSlashCommands(commands, '/xyz')).toEqual([]);
    expect(matchSlashCommands(commands, '/short').map((c) => c.name)).toEqual(['/summarize']);
  });
});
