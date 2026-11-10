import { create } from 'zustand';

export type ThemeMode = 'light' | 'dark' | 'system';

interface UiState {
  sidebarCollapsed: boolean;
  /** Width of the expanded sidebar in px (desktop); remembered on this device. */
  sidebarWidth: number;
  setSidebarWidth: (width: number) => void;
  artifactsOpen: boolean;
  /** The open files panel holds edits that are not saved (set by the panel; read by whatever closes it). */
  artifactsDirty: boolean;
  setArtifactsDirty: (dirty: boolean) => void;
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
// Device preferences, like the theme: global on purpose, not per user (see docs/frontend.md).
const SIDEBAR_WIDTH_KEY = 'my_ai_sidebar_width';
const SIDEBAR_COLLAPSED_KEY = 'my_ai_sidebar_collapsed';

export const SIDEBAR_MIN_WIDTH = 200;
export const SIDEBAR_MAX_WIDTH = 480;
export const SIDEBAR_DEFAULT_WIDTH = 256;
const PHONE_MAX_WIDTH = 768;

export function clampSidebarWidth(width: number): number {
  return Math.min(SIDEBAR_MAX_WIDTH, Math.max(SIDEBAR_MIN_WIDTH, Math.round(width)));
}

function isPhone(): boolean {
  return typeof window !== 'undefined' && window.innerWidth <= PHONE_MAX_WIDTH;
}

function readSidebarWidth(): number {
  const stored = Number(
    typeof localStorage === 'undefined' ? NaN : localStorage.getItem(SIDEBAR_WIDTH_KEY),
  );
  return Number.isFinite(stored) && stored > 0 ? clampSidebarWidth(stored) : SIDEBAR_DEFAULT_WIDTH;
}

/** The drawer always starts closed on a phone; elsewhere the remembered state wins. */
function readSidebarCollapsed(): boolean {
  if (isPhone()) return true;
  return typeof localStorage !== 'undefined' && localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === '1';
}

function rememberCollapsed(collapsed: boolean) {
  // Opening and closing the phone drawer is not a choice about the desktop sidebar.
  if (!isPhone()) localStorage.setItem(SIDEBAR_COLLAPSED_KEY, collapsed ? '1' : '0');
}

function readTheme(): ThemeMode {
  const stored = typeof localStorage === 'undefined' ? null : localStorage.getItem(THEME_KEY);
  return stored === 'light' || stored === 'dark' || stored === 'system' ? stored : 'system';
}

export const useUiStore = create<UiState>((set) => ({
  // Legacy: the sidebar starts closed on phones (<= 768px).
  sidebarCollapsed: readSidebarCollapsed(),
  sidebarWidth: readSidebarWidth(),
  setSidebarWidth: (width) => {
    // The phone drawer has a fixed width: nothing to remember.
    if (isPhone()) return;
    const next = clampSidebarWidth(width);
    localStorage.setItem(SIDEBAR_WIDTH_KEY, String(next));
    set({ sidebarWidth: next });
  },
  artifactsOpen: false,
  artifactsDirty: false,
  setArtifactsDirty: (dirty) => set({ artifactsDirty: dirty }),
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
  setSidebarCollapsed: (collapsed) => {
    rememberCollapsed(collapsed);
    set({ sidebarCollapsed: collapsed });
  },
  toggleSidebar: () => {
    const next = !useUiStore.getState().sidebarCollapsed;
    rememberCollapsed(next);
    set({ sidebarCollapsed: next });
  },
  setThemeMode: (mode) => {
    localStorage.setItem(THEME_KEY, mode);
    set({ themeMode: mode });
  },
}));
