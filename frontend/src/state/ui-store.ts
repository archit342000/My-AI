import { create } from 'zustand';

export type ThemeMode = 'light' | 'dark' | 'system';

interface UiState {
  sidebarCollapsed: boolean;
  artifactsOpen: boolean;
  themeMode: ThemeMode;
  toggleSidebar: () => void;
  toggleArtifacts: () => void;
  setThemeMode: (mode: ThemeMode) => void;
}

const THEME_KEY = 'my_ai_theme_mode';

function readTheme(): ThemeMode {
  const stored = typeof localStorage === 'undefined' ? null : localStorage.getItem(THEME_KEY);
  return stored === 'light' || stored === 'dark' || stored === 'system' ? stored : 'system';
}

export const useUiStore = create<UiState>((set) => ({
  sidebarCollapsed: false,
  artifactsOpen: false,
  themeMode: readTheme(),
  toggleArtifacts: () => set((s) => ({ artifactsOpen: !s.artifactsOpen })),
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  setThemeMode: (mode) => {
    localStorage.setItem(THEME_KEY, mode);
    set({ themeMode: mode });
  },
}));
