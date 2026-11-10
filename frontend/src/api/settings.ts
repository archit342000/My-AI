/** Settings, preferences, skills, personas, agents, browser and model endpoints (phase 5). */
import { apiJson, apiRequest } from './client';
import { readSse } from './sse';

export interface CodeRunnerSettings {
  code_runner_timeout: number;
  code_runner_memory_limit: string;
  code_runner_cpu_limit: string;
  code_runner_max_output_size: number;
}

export type ThinkingProfile = 'general' | 'none' | 'precision';

export interface AgentConfig {
  max_tokens: number;
  thinking_budget: number;
  thinking_profile: ThinkingProfile;
}

export interface Preference {
  id: string;
  content: string;
  tag: string;
  timestamp: number;
}

export interface Skill {
  id: string;
  name: string;
  description: string;
  instructions: string;
}

export interface Persona {
  id: string;
  name: string;
  content: string;
  is_default: number | boolean;
  research_mode: number | boolean;
  file_system_mode: number | boolean;
  browsing_mode: number | boolean;
}

/** Settings rarely change while the dialog is open; reopening within this window reuses cached data (F-54). */
export const SETTINGS_STALE_MS = 60_000;

export interface LoadedModel {
  id: string;
  status: { value: string };
}

/** What `GET /api/tools/config/settings` returns for the admin (the GitHub token itself never is). */
export type SystemSettings = CodeRunnerSettings & {
  code_runner_max_timeout?: number;
  github_pat_configured?: boolean;
  git_allowed_commands?: string[];
  git_known_commands?: string[];
} & Record<string, unknown>;

export const settingsApi = {
  getSystem: () => apiJson<SystemSettings>('/api/tools/config/settings'),
  /** Sends the GitHub token once; the server never returns it. */
  saveGitToken: (token: string) =>
    apiRequest('/api/tools/config/settings', { method: 'POST', json: { github_pat: token } }),
  saveGitAllowedCommands: (commands: string[]) =>
    apiRequest('/api/tools/config/settings', {
      method: 'POST',
      json: { git_allowed_commands: commands },
    }),
  saveCodeRunner: (body: CodeRunnerSettings) =>
    apiRequest('/api/tools/config/settings', { method: 'POST', json: body }),
  getAgents: () => apiJson<Record<string, AgentConfig>>('/api/tools/config/agents'),
  patchAgent: (name: string, body: AgentConfig) =>
    apiRequest(`/api/tools/config/agents/${encodeURIComponent(name)}`, {
      method: 'PATCH',
      json: body,
    }),
  getBrowser: () => apiJson<{ stealth_level: 'minimal' | 'advanced' }>('/api/tools/config/browser'),
  setBrowser: (level: 'minimal' | 'advanced') =>
    apiRequest('/api/tools/config/browser', { method: 'PATCH', json: { stealth_level: level } }),
  version: () => apiJson<{ version: string }>('/api/version'),
};

export const preferencesApi = {
  list: () =>
    apiJson<{ preferences: Preference[] }>('/api/tools/preferences').then((r) => r.preferences),
  create: (body: { content: string; tag: string }) =>
    apiRequest('/api/tools/preferences', { method: 'POST', json: body }),
  update: (id: string, body: { content: string; tag: string }) =>
    apiRequest(`/api/tools/preferences/${encodeURIComponent(id)}`, { method: 'PUT', json: body }),
  remove: (id: string) =>
    apiRequest(`/api/tools/preferences/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  reset: () => apiRequest('/api/tools/preferences/reset', { method: 'POST' }),
};

export const skillsApi = {
  list: () => apiJson<{ skills: Skill[] }>('/api/skills').then((r) => r.skills),
  create: (body: Omit<Skill, 'id'>) => apiRequest('/api/skills', { method: 'POST', json: body }),
  update: (id: string, body: Omit<Skill, 'id'>) =>
    apiRequest(`/api/skills/${encodeURIComponent(id)}`, { method: 'PUT', json: body }),
  remove: (id: string) => apiRequest(`/api/skills/${encodeURIComponent(id)}`, { method: 'DELETE' }),
};

export const personasApi = {
  list: () => apiJson<{ personas: Persona[] }>('/api/personas').then((r) => r.personas),
  create: (body: Omit<Persona, 'id'>) =>
    apiRequest('/api/personas', { method: 'POST', json: body }),
  update: (id: string, body: Omit<Persona, 'id'>) =>
    apiRequest(`/api/personas/${encodeURIComponent(id)}`, { method: 'PUT', json: body }),
  remove: (id: string) =>
    apiRequest(`/api/personas/${encodeURIComponent(id)}`, { method: 'DELETE' }),
};

/** `GET /api/models/config`: model ids by role (`general.text`, `research.main`, `vision`, `coder` ...). */
export interface ModelConfig {
  general?: Record<string, string>;
  research?: Record<string, string>;
}

export const modelsApi = {
  config: () => apiJson<ModelConfig>('/api/models/config'),
  list: () => apiJson<{ data: LoadedModel[] }>('/api/models/').then((r) => r.data),
  load: (model: string) => apiRequest('/api/models/load', { method: 'POST', json: { model } }),
  unload: (model: string) => apiRequest('/api/models/unload', { method: 'POST', json: { model } }),
};

/**
 * Runs the model speed test and yields its events (status lines, token deltas, timings, usage).
 * The server unloads every loaded model first. Throws on HTTP errors; aborting `signal` stops it.
 */
export async function* testSpeedStream(
  model: string,
  targetContextThreshold: number,
  signal: AbortSignal,
): AsyncGenerator<unknown> {
  const response = await apiRequest('/api/models/test-speed', {
    method: 'POST',
    json: { model, target_context_threshold: targetContextThreshold },
    signal,
  });
  if (!response.body) throw new Error('Empty response from server');
  yield* readSse(response.body);
}

export const settingsKeys = {
  system: ['settings', 'system'] as const,
  agents: ['settings', 'agents'] as const,
  browser: ['settings', 'browser'] as const,
  preferences: ['preferences'] as const,
  skills: ['skills'] as const,
  personas: ['personas'] as const,
  models: ['models'] as const,
  modelConfig: ['models', 'config'] as const,
  version: ['version'] as const,
};

/** The model config query: one definition so every observer of it shares the same options. */
export const modelConfigQuery = {
  queryKey: settingsKeys.modelConfig,
  queryFn: () => modelsApi.config(),
  staleTime: 300_000,
};
