import { useEffect, useRef, useState } from 'react';
import { IconButton } from '../components/ui/Button';
import { TickRule } from '../components/ui/TickRule';
import { isPhoneWidth } from '../lib/breakpoints';
import { pushModal } from '../lib/modal-stack';
import { trapFocus } from '../lib/focus-trap';
import { useQueryClient } from '@tanstack/react-query';
import { discardTemporaryChat, shouldDiscardTemporaryChat } from '../features/chat/temporary-chat';
import { Outlet, useLocation } from 'react-router';
import { AmbientBackground } from '../components/background/AmbientBackground';
import { ToastViewport } from '../components/ui/Toast';
import { usePlatformClass } from '../hooks/usePlatformClass';
import { useThemeSync } from '../hooks/useThemeSync';
import { useModalStore } from '../state/modal-store';
import { useUiStore } from '../state/ui-store';
import { useUserStore } from '../state/user-store';
import { discardNewChatDraft } from '../features/composer/draft-cleanup';
import { useDraftCleanup } from '../features/composer/useDraftCleanup';
import { FilesButton } from './FilesButton';
import { HeaderStatus } from './HeaderStatus';
import { PageTitleSlot } from './page-header-context';
import { Sidebar } from './Sidebar';
import { DialogHost } from '../features/settings/DialogHost';
import { Composer } from '../features/composer/Composer';

/** App frame: animated background, sidebar, routed main area, toasts. */
export function RootLayout() {
  const themeMode = useUiStore((s) => s.themeMode);
  const glassMode = useUiStore((s) => s.glassMode);
  useThemeSync(themeMode, glassMode);
  usePlatformClass();
  // The place in the header where the open page puts its title.
  const [titleSlot, setTitleSlot] = useState<HTMLElement | null>(null);
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
    if (isPhoneWidth()) useUiStore.getState().setSidebarCollapsed(true);
  }, [path]);
  // A dialog opened from the drawer covers the page, so the drawer closes (phone widths only).
  const dialogOpen = useModalStore((s) => s.open !== null);
  useEffect(() => {
    if (dialogOpen && isPhoneWidth()) useUiStore.getState().setSidebarCollapsed(true);
  }, [dialogOpen]);
  const sidebarCollapsed = useUiStore((s) => s.sidebarCollapsed);
  const sessionExpired = useUserStore((s) => s.sessionExpired);
  // On phones the sidebar is a drawer: Escape closes it (through the modal stack, so it stays
  // the top-most layer) and the scrim or the top bar button closes it.
  useEffect(() => {
    if (sidebarCollapsed || !isPhoneWidth()) return undefined;
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
          <button
            type="button"
            className="ui-button ui-button--secondary ui-button--sm"
            onClick={() => window.location.reload()}
          >
            Reload
          </button>
        </div>
      ) : null}
      <AmbientBackground />
      <div id="app-root">
        {sidebarCollapsed ? null : (
          <button
            type="button"
            className="sidebar-scrim"
            aria-label="Close the panel"
            onClick={() => useUiStore.getState().setSidebarCollapsed(true)}
          />
        )}
        <Sidebar />
        <main>
          <header className="main-head">
            <IconButton
              className="mobile-topbar"
              icon="menu"
              label={sidebarCollapsed ? 'Open the panel' : 'Close the panel'}
              tooltip={false}
              aria-expanded={!sidebarCollapsed}
              hidden={!sidebarCollapsed}
              onClick={() => useUiStore.getState().toggleSidebar()}
            />
            <div className="main-title" ref={setTitleSlot} />
            <div className="main-head__right">
              <HeaderStatus onSphere={path === '/'} />
              <FilesButton />
            </div>
          </header>
          <TickRule className="main-rule" />
          <PageTitleSlot.Provider value={titleSlot}>
            <Outlet />
          </PageTitleSlot.Provider>
          {/* One composer for the landing page and chats, so a route change never remounts it. */}
          {path === '/' || path.startsWith('/chat/') ? <Composer /> : null}
        </main>
      </div>
      <DialogHost />
      <ToastViewport />
    </>
  );
}
