import { WORKSPACE_ICON_PATHS } from './workspace-icons.generated';

/** Named icon keys: the workspace registry (from legacy icons.js) plus a few hand-drawn UI glyphs. */
export const UI_ICON_PATHS = {
  close: '<path d="M18 6L6 18M6 6l12 12" stroke-linecap="round" stroke-linejoin="round"/>',
  'chevron-left': '<path d="M15 6l-6 6 6 6" stroke-linecap="round" stroke-linejoin="round"/>',
  'chevron-right': '<path d="M9 18l6-6-6-6" stroke-linecap="round" stroke-linejoin="round"/>',
  'chevron-down': '<path d="M6 9l6 6 6-6" stroke-linecap="round" stroke-linejoin="round"/>',
  plus: '<path d="M12 5v14M5 12h14" stroke-linecap="round" stroke-linejoin="round"/>',
  logs: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/>',
  info: '<circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/>',
  error: '<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>',
  success: '<path d="M20 6L9 17l-5-5" stroke-linecap="round" stroke-linejoin="round"/>',
} as const;

export type UiIconName = keyof typeof UI_ICON_PATHS;
export type WorkspaceIconName = keyof typeof WORKSPACE_ICON_PATHS;
export type IconName = UiIconName | WorkspaceIconName;

export function iconPaths(name: IconName): string | undefined {
  if (name in UI_ICON_PATHS) return UI_ICON_PATHS[name as UiIconName];
  return (WORKSPACE_ICON_PATHS as Record<string, { paths: string } | undefined>)[name]?.paths;
}
