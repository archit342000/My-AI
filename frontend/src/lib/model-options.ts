import type { SelectOption } from '../components/ui/Select';

/** Minimal shape of a model from `/api/models/` (see api/settings.ts LoadedModel). */
export interface ModelLike {
  id: string;
  status: { value: string };
}

/** Ids of models that cannot answer chat: embedding models, placeholders and the `default` alias. */
const NON_CHAT = [/embedding/i, /^placeholder$/i, /^default$/i];

export function isChatModel(id: string): boolean {
  return !NON_CHAT.some((pattern) => pattern.test(id));
}

/** Status dot: loaded is green, loading is amber, anything else is muted. */
function dotFor(status: string): SelectOption['dot'] {
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
  const rank = (m: ModelLike) => (m.status.value === 'loaded' ? 0 : m.status.value === 'loading' ? 1 : 2);
  return [...models].sort((a, b) => rank(a) - rank(b) || a.id.localeCompare(b.id));
}

export function modelSelectOptions(models: ModelLike[]): SelectOption[] {
  return sortModels(models).map((m) => ({
    value: m.id,
    label: m.id,
    group: isChatModel(m.id) ? undefined : 'Other',
    dot: dotFor(m.status.value),
    hint: m.status.value === 'loaded' ? 'Loaded' : m.status.value === 'loading' ? 'Loading' : undefined,
  }));
}
