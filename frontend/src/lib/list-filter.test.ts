import { describe, expect, it } from 'vitest';
import type { Preference, Skill } from '../api/settings';
import { filterPreferences, filterSkills, tagsOf } from './list-filter';

const pref = (id: string, content: string, tag: string, timestamp: number): Preference => ({
  id,
  content,
  tag,
  timestamp,
});
const prefs = [
  pref('1', 'Answer in British English', 'preference', 100),
  pref('2', 'The project is called Atlas', 'project', 300),
  pref('3', 'I live in Leeds', 'personal_info', 200),
  pref('4', 'Use metric units', 'preference', 400),
];

describe('filterPreferences', () => {
  const all = { query: '', tag: '', sort: 'newest' as const };

  it('returns everything, newest first, for an empty query and no tag', () => {
    expect(filterPreferences(prefs, all).map((p) => p.id)).toEqual(['4', '2', '3', '1']);
  });

  it('matches the text case-insensitively on the content', () => {
    expect(filterPreferences(prefs, { ...all, query: 'ATLAS' }).map((p) => p.id)).toEqual(['2']);
    expect(filterPreferences(prefs, { ...all, query: '  leeds ' }).map((p) => p.id)).toEqual(['3']);
  });

  it('keeps one tag', () => {
    expect(filterPreferences(prefs, { ...all, tag: 'Preference' }).map((p) => p.id)).toEqual([
      '4',
      '1',
    ]);
  });

  it('orders oldest first on request, and combines the filters', () => {
    expect(filterPreferences(prefs, { ...all, sort: 'oldest' }).map((p) => p.id)).toEqual([
      '1',
      '3',
      '2',
      '4',
    ]);
    expect(
      filterPreferences(prefs, { query: 'use', tag: 'Preference', sort: 'oldest' }).map(
        (p) => p.id,
      ),
    ).toEqual(['4']);
  });

  it('does not change the input list', () => {
    const copy = [...prefs];
    filterPreferences(prefs, { ...all, sort: 'oldest' });
    expect(prefs).toEqual(copy);
  });
});

describe('filterSkills', () => {
  const skill = (name: string, description: string): Skill => ({
    id: name,
    name,
    description,
    instructions: '',
  });
  const skills = [
    skill('summarise', 'Summarise a long document'),
    skill('translate', 'Translate to French'),
  ];

  it('matches the name or the description, case-insensitively', () => {
    expect(filterSkills(skills, 'SUMM').map((s) => s.name)).toEqual(['summarise']);
    expect(filterSkills(skills, 'french').map((s) => s.name)).toEqual(['translate']);
  });

  it('returns the list as it is for an empty query', () => {
    expect(filterSkills(skills, '  ')).toBe(skills);
  });
});

describe('tagsOf', () => {
  it('lists each tag label once in first-seen order', () => {
    expect(tagsOf(prefs)).toEqual(['Preference', 'Project', 'Personal info']);
  });

  it('shows `preference` and `preferences` as one option that keeps both', () => {
    const mixed = [pref('1', 'a', 'preference', 1), pref('2', 'b', 'preferences', 2)];
    expect(tagsOf(mixed)).toEqual(['Preference']);
    expect(filterPreferences(mixed, { query: '', tag: 'Preference', sort: 'newest' })).toHaveLength(
      2,
    );
  });
});
