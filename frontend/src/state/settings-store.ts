import { create } from 'zustand';
import type { SamplingParams } from '../api/completions';
import { nsKey } from '../lib/user-storage';
import { useUserStore } from './user-store';

/**
 * Chat-level settings. Persisted under the same localStorage keys the legacy UI uses, so the
 * selected model, sampling values and mode toggles carry over. Every read and write goes through
 * `nsKey`, so each user has their own settings: the admin keeps these exact key names, any other
 * user gets `<key>:<userId>`. The store starts from defaults; `hydrate()` (called by `UserGate` once
 * the user is known) is the only place that reads storage.
 */
export const KEYS = {
  model: 'my_ai_selected_model',
  modelName: 'my_ai_selected_model_name',
  sampling: 'my_ai_sampling_params',
  research: 'my_ai_is_research_mode',
  vision: 'my_ai_vision_enabled',
  persona: 'my_ai_persona_id',
} as const;

export const DEFAULT_SAMPLING: SamplingParams = {
  max_tokens: 16384,
  thinking_budget_tokens: 2000,
  enable_thinking: true,
  thinking_profile: 'general',
};

function read(key: string): string | null {
  const namespaced = nsKey(key); // outside the try: a missing user is a bug to surface, not a storage error
  try {
    return localStorage.getItem(namespaced);
  } catch {
    return null;
  }
}

function write(key: string, value: string): void {
  localStorage.setItem(nsKey(key), value);
}

function loadSampling(): SamplingParams {
  try {
    const parsed = JSON.parse(read(KEYS.sampling) ?? '{}') as Partial<SamplingParams>;
    return { ...DEFAULT_SAMPLING, ...parsed };
  } catch {
    return DEFAULT_SAMPLING;
  }
}

const DEFAULT_MODES: ModeToggles = {
  researchMode: false,
  browsingMode: false,
  gitMode: false,
  codeExecutionMode: true,
  fileSystemMode: false,
};

export interface ModeToggles {
  researchMode: boolean;
  browsingMode: boolean;
  gitMode: boolean;
  codeExecutionMode: boolean;
  fileSystemMode: boolean;
}

interface SettingsState {
  model: string | null;
  modelName: string | null;
  sampling: SamplingParams;
  visionEnabled: boolean;
  /** Personalise replies from stored preferences (legacy `isUserPreferences`, default on). */
  userPreferences: boolean;
  personaId: string | null;
  modes: ModeToggles;
  /** Load this user's saved settings (call once the user is known). */
  hydrate: () => void;
  setPersona: (id: string | null) => void;
  setModel: (id: string, name: string) => void;
  setSampling: (patch: Partial<SamplingParams>) => void;
  setVisionEnabled: (on: boolean) => void;
  setUserPreferences: (on: boolean) => void;
  setMode: (key: keyof ModeToggles, on: boolean) => void;
}

export const useSettingsStore = create<SettingsState>((set, get) => ({
  model: null,
  modelName: null,
  sampling: DEFAULT_SAMPLING,
  visionEnabled: false,
  userPreferences: true,
  setUserPreferences: (on) => set({ userPreferences: on }),
  personaId: null,
  modes: DEFAULT_MODES,
  hydrate: () => {
    set({
      model: read(KEYS.model),
      modelName: read(KEYS.modelName),
      sampling: loadSampling(),
      visionEnabled: read(KEYS.vision) === 'true',
      personaId: read(KEYS.persona),
      // gitMode is admin only (the server refuses it otherwise); it is never persisted, so it starts off.
      modes: { ...DEFAULT_MODES, researchMode: read(KEYS.research) === 'true', gitMode: false },
    });
  },
  setPersona: (id) => {
    if (id) write(KEYS.persona, id);
    else localStorage.removeItem(nsKey(KEYS.persona));
    set({ personaId: id });
  },
  setModel: (id, name) => {
    write(KEYS.model, id);
    write(KEYS.modelName, name);
    set({ model: id, modelName: name });
  },
  setSampling: (patch) => {
    const next = { ...get().sampling, ...patch };
    write(KEYS.sampling, JSON.stringify(next));
    set({ sampling: next });
  },
  setVisionEnabled: (on) => {
    write(KEYS.vision, on ? 'true' : 'false');
    set({ visionEnabled: on });
  },
  setMode: (key, on) => {
    if (key === 'researchMode') write(KEYS.research, on ? 'true' : 'false');
    // A user cannot turn git mode on, whatever called this (the server would refuse it anyway).
    if (key === 'gitMode' && on && useUserStore.getState().user?.role !== 'admin') return;
    set({ modes: { ...get().modes, [key]: on } });
  },
}));
