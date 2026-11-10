import { useEffect, useRef } from 'react';
import { IconButton } from '../components/ui/Button';
import { pushModal } from '../lib/modal-stack';
import { trapFocus } from '../lib/focus-trap';
import { useQueryClient } from '@tanstack/react-query';
import { discardTemporaryChat, shouldDiscardTemporaryChat } from '../features/chat/temporary-chat';
import { Outlet, useLocation } from 'react-router';
import { AmbientBackground } from '../components/background/AmbientBackground';
import { ToastViewport } from '../components/ui/Toast';
import { useThemeSync } from '../hooks/useThemeSync';
import { useModalStore } from '../state/modal-store';
import { useUiStore } from '../state/ui-store';
import { useUserStore } from '../state/user-store';
import { discardNewChatDraft } from '../features/composer/draft-cleanup';
import { useDraftCleanup } from '../features/composer/useDraftCleanup';
import { useChatHasNoFiles } from '../features/artifacts/useChatHasNoFiles';
import { Sidebar } from './Sidebar';
import { DialogHost } from '../features/settings/DialogHost';
import { Composer } from '../features/composer/Composer';

/** App frame: animated background, sidebar, routed main area, toasts. */
export function RootLayout() {
  const themeMode = useUiStore((s) => s.themeMode);
  useThemeSync(themeMode);
  const toggleArtifacts = useUiStore((s) => s.toggleArtifacts);
  const queryClient = useQueryClient();
  // Unsent files are deleted when the page closes, whichever route is open.
  useDraftCleanup();
  const path = useLocation().pathname;
  const previousPath = useRef(path);
  // Leaving the landing page abandons a temporary chat. Keyed on the path only, so starting a chat
  // (which changes the id) never discards it.
  useEffect(() => {
    const hasTemporary = useUiStore.getState().temporaryChatId !== null;
    if (shouldDiscardTemporaryChat(previousPath.current, path, hasTemporary)) {
      void discardTemporaryChat(queryClient);
    }
    // Files staged for a new chat that was never sent are abandoned when the user leaves the landing page.
    // (A send clears them first, so starting a chat never gets here with files.)
    if (previousPath.current === '/' && path !== '/') void discardNewChatDraft(queryClient);
    previousPath.current = path;
  }, [path, queryClient]);
  // On phones the sidebar overlays the page, so close it after navigating.
  useEffect(() => {
    if (window.innerWidth <= 768) useUiStore.getState().setSidebarCollapsed(true);
  }, [path]);
  // A dialog opened from the drawer covers the page, so the drawer closes (phone widths only).
  const dialogOpen = useModalStore((s) => s.open !== null);
  useEffect(() => {
    if (dialogOpen && window.innerWidth <= 768) useUiStore.getState().setSidebarCollapsed(true);
  }, [dialogOpen]);
  const onLogs = useLocation().pathname.startsWith('/logs');
  const noFiles = useChatHasNoFiles();
  const sidebarCollapsed = useUiStore((s) => s.sidebarCollapsed);
  const sessionExpired = useUserStore((s) => s.sessionExpired);
  // On phones the sidebar is a drawer: Escape closes it (through the modal stack, so it stays
  // the top-most layer) and the scrim or the top bar button closes it.
  useEffect(() => {
    if (sidebarCollapsed || window.innerWidth > 768) return undefined;
    const drawer = document.getElementById('sidebar');
    const releaseTrap = drawer ? trapFocus(drawer) : undefined;
    const releaseModal = pushModal(() => useUiStore.getState().setSidebarCollapsed(true));
    return () => {
      releaseModal();
      releaseTrap?.();
    };
  }, [sidebarCollapsed]);

  return (
    <>
      {sessionExpired ? (
        <div className="session-banner" role="alert">
          <span>Your session has expired.</span>
          <button type="button" className="btn-secondary" onClick={() => window.location.reload()}>
            Reload
          </button>
        </div>
      ) : null}
      {/* The logs page has an opaque surface; the particle canvas would only compete with the data (F-52). */}
      {onLogs ? null : <AmbientBackground />}
      <div id="app-root">
        <IconButton
          className="mobile-topbar"
          icon="menu"
          label={sidebarCollapsed ? 'Open sidebar' : 'Close sidebar'}
          tooltip={false}
          aria-expanded={!sidebarCollapsed}
          hidden={!sidebarCollapsed}
          onClick={() => useUiStore.getState().toggleSidebar()}
        />
        {sidebarCollapsed ? null : (
          <button
            type="button"
            className="sidebar-scrim"
            aria-label="Close sidebar"
            onClick={() => useUiStore.getState().setSidebarCollapsed(true)}
          />
        )}
        <Sidebar />
        <main>
          {onLogs ? null : (
            <button
              id="nav-files-btn"
              type="button"
              className={`btn-secondary glass top-right-btn${noFiles ? ' top-right-btn--empty' : ''}`}
              title="View Files / Artifacts"
              aria-label="View files and artifacts"
              disabled={path === '/'}
              onClick={toggleArtifacts}
            >
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
                aria-hidden="true"
              >
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
              </svg>
            </button>
          )}
          <Outlet />
          {/* One composer for the landing page and chats, so a route change never remounts it. */}
          {path === '/' || path.startsWith('/chat/') ? <Composer /> : null}
        </main>
      </div>
      <DialogHost />
      <ToastViewport />
    </>
  );
}
