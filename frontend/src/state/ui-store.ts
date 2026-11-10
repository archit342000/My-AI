import { create } from 'zustand';

export type ThemeMode = 'light' | 'dark' | 'system';

interface UiState {
  sidebarCollapsed: boolean;
  artifactsOpen: boolean;
  /** True while a page that has a files drawer is open (a file link can be followed there). */
  filesAvailable: boolean;
  setFilesAvailable: (available: boolean) => void;
  /** A file the transcript asked the files panel to select (by title or file name), or null. */
  requestedArtifactPath: string | null;
  /** Opens the files drawer and asks it to select `path`. */
  openArtifact: (path: string) => void;
  clearRequestedArtifact: () => void;
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
  filesAvailable: false,
  setFilesAvailable: (available) => set({ filesAvailable: available }),
  requestedArtifactPath: null,
  openArtifact: (path) => set({ artifactsOpen: true, requestedArtifactPath: path }),
  clearRequestedArtifact: () => set({ requestedArtifactPath: null }),
  themeMode: readTheme(),
  temporaryChatId: null,
  setTemporaryChatId: (id) => set({ temporaryChatId: id }),
  newChatWorkspaceId: null,
  setNewChatWorkspaceId: (id) => set({ newChatWorkspaceId: id }),
  // Closing the drawer also drops a file request it never answered.
  toggleArtifacts: () =>
    set((s) => ({
      artifactsOpen: !s.artifactsOpen,
      requestedArtifactPath: s.artifactsOpen ? null : s.requestedArtifactPath,
    })),
  setArtifactsOpen: (open) =>
    set((s) => ({ artifactsOpen: open, requestedArtifactPath: open ? s.requestedArtifactPath : null })),
  setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  setThemeMode: (mode) => {
    localStorage.setItem(THEME_KEY, mode);
    set({ themeMode: mode });
  },
}));
