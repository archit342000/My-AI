/**
 * Display labels for internal identifiers (plan F-29). Internal names stay in the API; the UI shows
 * these. Unknown keys fall back to a title-cased form of the raw name, never the raw name itself.
 */

const THINKING_PROFILE_LABELS: Record<string, string> = {
  general: 'General',
  precision: 'Precision',
  none: 'None',
};

const AGENT_LABELS: Record<string, string> = {
  browsing_agent: 'Browsing agent',
  code_agent: 'Code agent',
  research_agent: 'Research agent',
  file_agent: 'File agent',
};

const MEMORY_TAG_LABELS: Record<string, string> = {
  personal_info: 'Personal info',
  preference: 'Preference',
  preferences: 'Preference',
  project: 'Project',
  general: 'General',
};

/** `personal_info` becomes `Personal info`; hyphens and underscores both split words. */
export function titleCase(raw: string): string {
  const words = raw.replace(/[_-]+/g, ' ').trim().toLowerCase().split(/\s+/).filter(Boolean);
  if (words.length === 0) return '';
  const [first, ...rest] = words;
  return [first!.charAt(0).toUpperCase() + first!.slice(1), ...rest].join(' ');
}

export function thinkingProfileLabel(profile: string): string {
  return THINKING_PROFILE_LABELS[profile] ?? titleCase(profile);
}

export function agentLabel(name: string): string {
  return AGENT_LABELS[name] ?? titleCase(name);
}

export function memoryTagLabel(tag: string): string {
  return MEMORY_TAG_LABELS[tag] ?? titleCase(tag);
}

const LANGUAGE_LABELS: Record<string, string> = {
  typescript: 'TypeScript',
  ts: 'TypeScript',
  tsx: 'TypeScript',
  javascript: 'JavaScript',
  js: 'JavaScript',
  jsx: 'JavaScript',
  python: 'Python',
  py: 'Python',
  markdown: 'Markdown',
  md: 'Markdown',
  json: 'JSON',
  html: 'HTML',
  css: 'CSS',
  sql: 'SQL',
  yaml: 'YAML',
  yml: 'YAML',
  xml: 'XML',
  csv: 'CSV',
  bash: 'Shell',
  sh: 'Shell',
  shell: 'Shell',
  text: 'Plain text',
  plaintext: 'Plain text',
  txt: 'Plain text',
  cpp: 'C++',
  csharp: 'C#',
  php: 'PHP',
};

/** A file's language as its proper name: `typescript` becomes `TypeScript`. */
export function languageLabel(language: string): string {
  return LANGUAGE_LABELS[language.toLowerCase()] ?? titleCase(language);
}

/** Who made a version of a file, in the app's words: the model is "My AI", the person is "You". */
export function authorLabel(author: string | null | undefined): string {
  if (!author) return '';
  const key = author.toLowerCase();
  if (key === 'assistant' || key === 'ai' || key === 'model') return 'My AI';
  if (key === 'user' || key === 'human') return 'You';
  return author;
}
