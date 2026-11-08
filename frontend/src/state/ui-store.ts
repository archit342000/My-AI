import { create } from 'zustand';

export type ThemeMode = 'light' | 'dark' | 'system';

interface UiState {
  sidebarCollapsed: boolean;
  artifactsOpen: boolean;
  themeMode: ThemeMode;
  /** Id of the active temporary chat (not listed, deleted when abandoned), or null. */
  temporaryChatId: string | null;
  setTemporaryChatId: (id: string | null) => void;
  /** Workspace that the next new chat is filed into (set by "New chat in this workspace"). */
  newChatWorkspaceId: string | null;
  setNewChatWorkspaceId: (id: string | null) => void;
  toggleSidebar: () => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  toggleArtifacts: () => void;
  setArtifactsOpen: (open: boolean) => void;
  setThemeMode: (mode: ThemeMode) => void;
}

const THEME_KEY = 'my_ai_theme_mode';

function readTheme(): ThemeMode {
  const stored = typeof localStorage === 'undefined' ? null : localStorage.getItem(THEME_KEY);
  return stored === 'light' || stored === 'dark' || stored === 'system' ? stored : 'system';
}

export const useUiStore = create<UiState>((set) => ({
  // Legacy: the sidebar starts closed on phones (<= 768px).
  sidebarCollapsed: typeof window !== 'undefined' && window.innerWidth <= 768,
  artifactsOpen: false,
  themeMode: readTheme(),
  temporaryChatId: null,
  setTemporaryChatId: (id) => set({ temporaryChatId: id }),
  newChatWorkspaceId: null,
  setNewChatWorkspaceId: (id) => set({ newChatWorkspaceId: id }),
  toggleArtifacts: () => set((s) => ({ artifactsOpen: !s.artifactsOpen })),
  setArtifactsOpen: (open) => set({ artifactsOpen: open }),
  setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  setThemeMode: (mode) => {
    localStorage.setItem(THEME_KEY, mode);
    set({ themeMode: mode });
  },
}));
