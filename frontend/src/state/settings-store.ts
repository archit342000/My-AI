import { create } from 'zustand';
import type { SamplingParams } from '../api/completions';
import type { ChatDetail } from '../api/types';
import { isAbsent } from '../lib/chat-model';
import { enableThinkingFor } from '../lib/thinking';
import { nsKey } from '../lib/user-storage';
import { useUserStore } from './user-store';

/**
 * Chat-level settings. Persisted under the same localStorage keys the legacy UI uses, so the
 * selected model, sampling values and mode toggles carry over. Every read and write goes through
 * `nsKey`, so each user has their own settings: the admin keeps these exact key names, any other
 * user gets `<key>:<userId>`. The store starts from defaults; `hydrate()` (called by `UserGate` once
 * the user is known) is the only place that reads storage.
 *
 * The store holds the active values (what the next send uses) and a `defaults` snapshot (what a new
 * chat starts from, mirrored in storage). Opening a chat copies its own values over the active ones
 * (`applyChat`); leaving it copies the defaults back (`resetToDefaults`). While a chat's values are
 * active the setters change the active values only, so one chat's settings never become the defaults.
 */
export const KEYS = {
  model: 'my_ai_selected_model',
  modelName: 'my_ai_selected_model_name',
  sampling: 'my_ai_sampling_params',
  research: 'my_ai_is_research_mode',
  vision: 'my_ai_vision_enabled',
  persona: 'my_ai_persona_id',
  /** JSON of the file-system, browsing and code-execution toggles (research mode has its own key). */
  modes: 'my_ai_modes',
  /** Legacy object of new-chat defaults; only its `userPreferences` field is used here. */
  chatDefaults: 'my_ai_chat_defaults',
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
    const merged = { ...DEFAULT_SAMPLING, ...parsed };
    // Values saved before the profile decided it can say {none, thinking on}; the profile wins.
    return { ...merged, enable_thinking: enableThinkingFor(merged.thinking_profile) };
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

/** The persisted part of the mode toggles (research mode and git mode are kept elsewhere or not at all). */
type StoredModes = Pick<ModeToggles, 'fileSystemMode' | 'browsingMode' | 'codeExecutionMode'>;

function loadModes(): ModeToggles {
  let parsed: unknown = {};
  try {
    parsed = JSON.parse(read(KEYS.modes) ?? '{}');
  } catch {
    parsed = {};
  }
  // Anything but an object of booleans (corrupt or hand-edited storage) falls back to the defaults.
  const stored: Record<string, unknown> =
    typeof parsed === 'object' && parsed !== null && !Array.isArray(parsed)
      ? (parsed as Record<string, unknown>)
      : {};
  const bool = (key: keyof StoredModes): boolean =>
    typeof stored[key] === 'boolean' ? (stored[key] as boolean) : DEFAULT_MODES[key];
  return {
    ...DEFAULT_MODES,
    researchMode: read(KEYS.research) === 'true',
    fileSystemMode: bool('fileSystemMode'),
    browsingMode: bool('browsingMode'),
    codeExecutionMode: bool('codeExecutionMode'),
    // gitMode is admin only (the server refuses it otherwise); it is never persisted, so it starts off.
    gitMode: false,
  };
}

function readChatDefaults(): Record<string, unknown> {
  try {
    const parsed: unknown = JSON.parse(read(KEYS.chatDefaults) ?? '{}');
    return typeof parsed === 'object' && parsed !== null ? (parsed as Record<string, unknown>) : {};
  } catch {
    return {};
  }
}

function loadUserPreferences(): boolean {
  const value = readChatDefaults().userPreferences;
  return typeof value === 'boolean' ? value : true;
}

/** What a new chat starts from. */
interface Defaults {
  model: string | null;
  modelName: string | null;
  sampling: SamplingParams;
  userPreferences: boolean;
  personaId: string | null;
  modes: ModeToggles;
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
  /** New-chat defaults, mirrored in storage. */
  defaults: Defaults;
  /** True while an opened chat's own values are the active ones. */
  chatScoped: boolean;
  /** Load this user's saved settings (call once the user is known). */
  hydrate: () => void;
  /**
   * Called as soon as a chat page opens, before its values have loaded: from here the setters change
   * the active values only, so nothing the user does in the chat becomes a new-chat default.
   */
  enterChat: () => void;
  /** Make the opened chat's saved values the active ones; `models` is the loaded model list. */
  applyChat: (detail: ChatDetail, models: ReadonlyArray<{ id: string }>) => void;
  /** Make the new-chat defaults the active values again. */
  resetToDefaults: () => void;
  setPersona: (id: string | null) => void;
  setModel: (id: string, name: string) => void;
  setSampling: (patch: Partial<SamplingParams>) => void;
  setVisionEnabled: (on: boolean) => void;
  setUserPreferences: (on: boolean) => void;
  setMode: (key: keyof ModeToggles, on: boolean) => void;
}

const BASE_DEFAULTS: Defaults = {
  model: null,
  modelName: null,
  sampling: DEFAULT_SAMPLING,
  userPreferences: true,
  personaId: null,
  modes: DEFAULT_MODES,
};

/** A saved flag as a boolean, or undefined when the chat has no value for it. */
function flag(value: unknown): boolean | undefined {
  if (isAbsent(value)) return undefined;
  return value === true || value === 1 || value === '1' || value === 'true';
}

/** A saved number, or undefined when absent or not a number. */
function num(value: unknown): number | undefined {
  if (isAbsent(value)) return undefined;
  const n = Number(value);
  return Number.isFinite(n) ? n : undefined;
}

export const useSettingsStore = create<SettingsState>((set, get) => ({
  ...BASE_DEFAULTS,
  visionEnabled: false,
  defaults: BASE_DEFAULTS,
  chatScoped: false,
  setUserPreferences: (on) => {
    if (!get().chatScoped) {
      write(KEYS.chatDefaults, JSON.stringify({ ...readChatDefaults(), userPreferences: on }));
      set({ defaults: { ...get().defaults, userPreferences: on } });
    }
    set({ userPreferences: on });
  },
  hydrate: () => {
    const defaults: Defaults = {
      model: read(KEYS.model),
      modelName: read(KEYS.modelName),
      sampling: loadSampling(),
      userPreferences: loadUserPreferences(),
      personaId: read(KEYS.persona),
      modes: loadModes(),
    };
    set({
      ...defaults,
      defaults,
      chatScoped: false,
      visionEnabled: read(KEYS.vision) === 'true',
    });
  },
  enterChat: () => set({ chatScoped: true }),
  applyChat: (detail, models) => {
    const isAdmin = useUserStore.getState().user?.role === 'admin';
    const current = get();
    const patch: Partial<SettingsState> = { chatScoped: true };

    if (!isAbsent(detail.last_model) && models.some((m) => m.id === detail.last_model)) {
      patch.model = String(detail.last_model);
      patch.modelName = String(detail.last_model);
    }

    const modes = { ...current.modes };
    const research = flag(detail.research_mode);
    const files = flag(detail.file_system_mode);
    const browsing = flag(detail.browsing_mode);
    const code = flag(detail.code_execution_mode);
    const git = flag(detail.git_mode);
    if (research !== undefined) modes.researchMode = research;
    if (files !== undefined) modes.fileSystemMode = files;
    if (browsing !== undefined) modes.browsingMode = browsing;
    if (code !== undefined) modes.codeExecutionMode = code;
    if (git !== undefined && isAdmin) modes.gitMode = git;
    patch.modes = modes;

    const prefs = flag(detail.user_preferences);
    if (prefs !== undefined) patch.userPreferences = prefs;
    // A chat stores NULL for "no persona", which must not inherit the default one; a detail without
    // the field at all (the seeded copy of a new chat) leaves the current persona alone.
    if (detail.persona_id !== undefined) {
      patch.personaId = isAbsent(detail.persona_id) ? null : String(detail.persona_id);
    }

    const sampling = { ...current.sampling };
    const maxTokens = num(detail.max_tokens);
    const budget = num(detail.thinking_budget_tokens);
    if (maxTokens !== undefined) sampling.max_tokens = maxTokens;
    if (budget !== undefined) sampling.thinking_budget_tokens = budget;
    if (!isAbsent(detail.thinking_profile))
      sampling.thinking_profile = String(detail.thinking_profile);
    // Whatever the row says, thinking follows the profile.
    sampling.enable_thinking = enableThinkingFor(sampling.thinking_profile);
    // The server stores 1.0 when a chat never set these, so only another value means "set".
    const temperature = num(detail.temperature);
    const topP = num(detail.top_p);
    // 1.0 means the chat never set it: show the model default instead of the new-chat default.
    if (temperature !== undefined)
      sampling.temperature = temperature !== 1 ? temperature : undefined;
    if (topP !== undefined) sampling.top_p = topP !== 1 ? topP : undefined;
    patch.sampling = sampling;

    set(patch);
  },
  resetToDefaults: () => {
    const { defaults } = get();
    set({ ...defaults, chatScoped: false });
  },
  setPersona: (id) => {
    if (!get().chatScoped) {
      if (id) write(KEYS.persona, id);
      else localStorage.removeItem(nsKey(KEYS.persona));
      set({ defaults: { ...get().defaults, personaId: id } });
    }
    set({ personaId: id });
  },
  setModel: (id, name) => {
    if (!get().chatScoped) {
      write(KEYS.model, id);
      write(KEYS.modelName, name);
      set({ defaults: { ...get().defaults, model: id, modelName: name } });
    }
    set({ model: id, modelName: name });
  },
  setSampling: (patch) => {
    const next = { ...get().sampling, ...patch };
    // The profile decides whether thinking is on.
    if (patch.thinking_profile !== undefined)
      next.enable_thinking = enableThinkingFor(next.thinking_profile);
    if (!get().chatScoped) {
      write(KEYS.sampling, JSON.stringify(next));
      set({ defaults: { ...get().defaults, sampling: next } });
    }
    set({ sampling: next });
  },
  setVisionEnabled: (on) => {
    write(KEYS.vision, on ? 'true' : 'false');
    set({ visionEnabled: on });
  },
  setMode: (key, on) => {
    // A user cannot turn git mode on, whatever called this (the server would refuse it anyway).
    if (key === 'gitMode' && on && useUserStore.getState().user?.role !== 'admin') return;
    const modes = { ...get().modes, [key]: on };
    if (!get().chatScoped) {
      if (key === 'researchMode') write(KEYS.research, on ? 'true' : 'false');
      else if (key !== 'gitMode') {
        const stored: StoredModes = {
          fileSystemMode: modes.fileSystemMode,
          browsingMode: modes.browsingMode,
          codeExecutionMode: modes.codeExecutionMode,
        };
        write(KEYS.modes, JSON.stringify(stored));
      }
      set({ defaults: { ...get().defaults, modes: { ...get().defaults.modes, [key]: on } } });
    }
    set({ modes });
  },
}));
