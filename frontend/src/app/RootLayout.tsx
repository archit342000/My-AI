import { Outlet } from 'react-router';
import { AmbientBackground } from '../components/background/AmbientBackground';
import { ToastViewport } from '../components/ui/Toast';
import { useThemeSync } from '../hooks/useThemeSync';
import { useUiStore } from '../state/ui-store';
import { Sidebar } from './Sidebar';
import { DialogHost } from '../features/settings/DialogHost';

/** App frame: animated background, sidebar, routed main area, toasts. */
export function RootLayout() {
  const themeMode = useUiStore((s) => s.themeMode);
  useThemeSync(themeMode);

  return (
    <>
      <AmbientBackground />
      <div id="app-root">
        <Sidebar />
        <main>
          <button id="nav-files-btn" type="button" className="btn-secondary glass top-right-btn" title="View Files / Artifacts" aria-label="View files and artifacts">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
            </svg>
          </button>
          <Outlet />
        </main>
      </div>
      <DialogHost />
      <ToastViewport />
    </>
  );
}
