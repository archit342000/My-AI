import type { ModelConfig } from '../api/settings';
import type { SelectOption } from '../components/ui/Select';

/** Minimal shape of a model from `/api/models/` (see api/settings.ts LoadedModel). */
export interface ModelLike {
  id: string;
  /** Absent when the upstream gives no status object (F8): treated as unknown, never a crash. */
  status?: { value: string };
}

/** Ids of models that cannot answer chat: embedding models, placeholders and the `default` alias. */
const NON_CHAT = [/embedding/i, /^placeholder$/i, /^default$/i];

export function isChatModel(id: string): boolean {
  return !NON_CHAT.some((pattern) => pattern.test(id));
}

/** Status dot: loaded is green, loading is amber, anything else is muted. */
function statusOf(m: ModelLike): string | undefined {
  return m.status?.value;
}

function dotFor(status: string | undefined): SelectOption['dot'] {
  if (status === 'loaded') return 'success';
  if (status === 'loading') return 'warning';
  return 'off';
}

/**
 * Options for the model picker (plan F-25). Chat models come first, loaded ones before the rest;
 * non-chat models are kept under an "Other" group so they remain reachable.
 */
/** Loaded models first, then loading, then the rest; ties sort by id. */
export function sortModels<T extends ModelLike>(models: T[]): T[] {
  const rank = (m: ModelLike) => (statusOf(m) === 'loaded' ? 0 : statusOf(m) === 'loading' ? 1 : 2);
  return [...models].sort((a, b) => rank(a) - rank(b) || a.id.localeCompare(b.id));
}

export function modelSelectOptions(models: ModelLike[]): SelectOption[] {
  return sortModels(models).map((m) => ({
    value: m.id,
    label: m.id,
    group: isChatModel(m.id) ? undefined : 'Other',
    dot: dotFor(statusOf(m)),
    hint: statusOf(m) === 'loaded' ? 'Loaded' : statusOf(m) === 'loading' ? 'Loading' : undefined,
  }));
}

const ROLE_NAMES: Record<string, string> = {
  main: 'Research Main',
  text: 'General Text',
  vision: 'General Vision',
  vision2: 'General Vision (High)',
  coder: 'General Coder',
};

/**
 * Display names by model id, as the legacy model picker builds them from `/api/models/config`:
 * `<role name> (<last path segment of the id>)`. A model listed in two roles keeps the later one
 * (research roles are read first, then general), as the legacy map does.
 */
export function modelDisplayNames(config: ModelConfig): Map<string, string> {
  const names = new Map<string, string>();
  for (const group of [config.research, config.general]) {
    for (const [role, id] of Object.entries(group ?? {})) {
      if (typeof id !== 'string') continue;
      const base = ROLE_NAMES[role] ?? role.charAt(0).toUpperCase() + role.slice(1);
      names.set(id, `${base} (${id.split('/').pop() || id})`);
    }
  }
  return names;
}

/** The display name of a model id, or the id itself when the config does not name it. */
export function displayModelName(id: string, names: Map<string, string>): string {
  return names.get(id) ?? id;
}
