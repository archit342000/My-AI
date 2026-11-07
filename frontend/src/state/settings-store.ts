import { create } from 'zustand';
import type { SamplingParams } from '../api/completions';

/**
 * Chat-level settings. Persisted under the same localStorage keys the legacy UI uses, so the
 * selected model, sampling values and mode toggles carry over.
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
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function loadSampling(): SamplingParams {
  try {
    const parsed = JSON.parse(read(KEYS.sampling) ?? '{}') as Partial<SamplingParams>;
    return { ...DEFAULT_SAMPLING, ...parsed };
  } catch {
    return DEFAULT_SAMPLING;
  }
}

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
  personaId: string | null;
  modes: ModeToggles;
  setPersona: (id: string | null) => void;
  setModel: (id: string, name: string) => void;
  setSampling: (patch: Partial<SamplingParams>) => void;
  setVisionEnabled: (on: boolean) => void;
  setMode: (key: keyof ModeToggles, on: boolean) => void;
}

export const useSettingsStore = create<SettingsState>((set, get) => ({
  model: read(KEYS.model),
  modelName: read(KEYS.modelName),
  sampling: loadSampling(),
  visionEnabled: read(KEYS.vision) === 'true',
  personaId: read(KEYS.persona),
  setPersona: (id) => {
    if (id) localStorage.setItem(KEYS.persona, id);
    else localStorage.removeItem(KEYS.persona);
    set({ personaId: id });
  },
  modes: {
    researchMode: read(KEYS.research) === 'true',
    browsingMode: false,
    gitMode: false,
    codeExecutionMode: true,
    fileSystemMode: false,
  },
  setModel: (id, name) => {
    localStorage.setItem(KEYS.model, id);
    localStorage.setItem(KEYS.modelName, name);
    set({ model: id, modelName: name });
  },
  setSampling: (patch) => {
    const next = { ...get().sampling, ...patch };
    localStorage.setItem(KEYS.sampling, JSON.stringify(next));
    set({ sampling: next });
  },
  setVisionEnabled: (on) => {
    localStorage.setItem(KEYS.vision, on ? 'true' : 'false');
    set({ visionEnabled: on });
  },
  setMode: (key, on) => {
    if (key === 'researchMode') localStorage.setItem(KEYS.research, on ? 'true' : 'false');
    set({ modes: { ...get().modes, [key]: on } });
  },
}));
