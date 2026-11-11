/** A sent message longer than this many characters, or lines, is folded until "Read more". */
export const FOLD_CHARS = 600;
export const FOLD_LINES = 8;

/** True when a sent message is long enough to fold. */
export function isLongMessage(text: string): boolean {
  return text.length > FOLD_CHARS || text.split('\n').length > FOLD_LINES;
}

/**
 * Splits a leading slash command ("/summarise the paper") from the rest, so the skill's name can be
 * highlighted. Only a command at the very start counts, and only a plain name (letters, digits,
 * dashes, underscores).
 */
export function splitSkill(text: string): { skill: string | null; rest: string } {
  const match = /^(\/[A-Za-z][\w-]*)(?=\s|$)/.exec(text);
  if (!match) return { skill: null, rest: text };
  const skill = match[1] ?? null;
  return { skill, rest: text.slice(skill ? skill.length : 0).replace(/^[ \t]+/, '') };
}
