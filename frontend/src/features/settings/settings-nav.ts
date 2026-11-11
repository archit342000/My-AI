import { useCallback } from 'react';
import { useLocation, useNavigate } from 'react-router';
import type { IconName } from '../../components/icons/icon-paths';

/** The parts of the settings page, in the order they are listed. */
export const SETTINGS_SECTIONS = [
  { id: 'chat', label: 'Chat', icon: 'message-square', admin: false },
  { id: 'models', label: 'Models', icon: 'chip', admin: true },
  { id: 'personas', label: 'Personas', icon: 'user', admin: false },
  { id: 'skills', label: 'Skills', icon: 'zap', admin: false },
  { id: 'memory', label: 'Memory', icon: 'bookmark', admin: false },
  { id: 'agents', label: 'Agents', icon: 'nodes', admin: true },
  { id: 'system', label: 'System', icon: 'sliders', admin: false },
] as const satisfies ReadonlyArray<{ id: string; label: string; icon: IconName; admin: boolean }>;

export type SettingsSectionId = (typeof SETTINGS_SECTIONS)[number]['id'];

/** The name of the address-bar value that says the settings page is open, and at which part. */
export const SETTINGS_PARAM = 'settings';

/** The section a search string asks for, or null when the settings page is not open. */
export function sectionFromSearch(search: string): SettingsSectionId | null {
  const value = new URLSearchParams(search).get(SETTINGS_PARAM);
  if (value === null) return null;
  return SETTINGS_SECTIONS.find((s) => s.id === value)?.id ?? 'chat';
}

/** The same address with the settings page open at a part (or closed, for null). */
export function searchWithSection(search: string, section: SettingsSectionId | null): string {
  const params = new URLSearchParams(search);
  if (section === null) params.delete(SETTINGS_PARAM);
  else params.set(SETTINGS_PARAM, section);
  const text = params.toString();
  return text ? `?${text}` : '';
}

/**
 * Opens the settings page over the page that is on screen. That page stays as it is underneath (a
 * chat keeps its own settings and an answer keeps arriving), and Back returns to it.
 */
export function useOpenSettings(): (section: SettingsSectionId) => void {
  const navigate = useNavigate();
  const location = useLocation();
  return useCallback(
    (section) => {
      const open = sectionFromSearch(location.search) !== null;
      navigate(
        { pathname: location.pathname, search: searchWithSection(location.search, section) },
        // Opening adds a step to go back over; moving between parts does not.
        { replace: open, state: { ...(location.state as object | null), settingsOpened: true } },
      );
    },
    [navigate, location],
  );
}
