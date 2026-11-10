/** Thinking profiles and whether each one turns model thinking on (legacy `THINKING_PROFILES`). */
const THINKING_OFF = new Set(['none']);

/** `enable_thinking` for a profile: "none" turns thinking off, every other profile leaves it on. */
export function enableThinkingFor(profile: string): boolean {
  return !THINKING_OFF.has(profile);
}
