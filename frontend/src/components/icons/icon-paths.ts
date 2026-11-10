import { WORKSPACE_ICON_PATHS } from './workspace-icons.generated';

/** Named icon keys: the workspace registry (from legacy icons.js) plus a few hand-drawn UI glyphs. */
export const UI_ICON_PATHS = {
  close: '<path d="M18 6L6 18M6 6l12 12" stroke-linecap="round" stroke-linejoin="round"/>',
  menu: '<path d="M4 6h16M4 12h16M4 18h16" stroke-linecap="round"/>',
  'chevron-left': '<path d="M15 6l-6 6 6 6" stroke-linecap="round" stroke-linejoin="round"/>',
  'chevron-right': '<path d="M9 18l6-6-6-6" stroke-linecap="round" stroke-linejoin="round"/>',
  'chevron-down': '<path d="M6 9l6 6 6-6" stroke-linecap="round" stroke-linejoin="round"/>',
  plus: '<path d="M12 5v14M5 12h14" stroke-linecap="round" stroke-linejoin="round"/>',
  'grid-plus':
    '<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><line x1="17.5" y1="14" x2="17.5" y2="21"/><line x1="14" y1="17.5" x2="21" y2="17.5"/>',
  logs: '<path d="M15 12h-5M15 8h-5M19 17V5a2 2 0 0 0-2-2H4"/><path d="M8 21h12a2 2 0 0 0 2-2v-1a1 1 0 0 0-1-1H11a1 1 0 0 0-1 1v1a2 2 0 1 1-4 0V5a2 2 0 1 0-4 0v2a1 1 0 0 0 1 1h3"/>',
  info: '<circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/>',
  error:
    '<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>',
  success: '<path d="M20 6L9 17l-5-5" stroke-linecap="round" stroke-linejoin="round"/>',
  check: '<path d="M20 6L9 17l-5-5" stroke-linecap="round" stroke-linejoin="round"/>',
  minus: '<path d="M6 12h12"/>',
  copy: '<rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',
  'refresh-cw':
    '<path d="M23 4v6h-6M1 20v-6h6"/><path d="M3.5 9a9 9 0 0 1 14.9-3.4L23 10M1 14l4.6 4.4A9 9 0 0 0 20.5 15"/>',
  'scroll-text':
    '<path d="M15 12h-5M15 8h-5M19 17V5a2 2 0 0 0-2-2H4"/><path d="M8 21h12a2 2 0 0 0 2-2v-1a1 1 0 0 0-1-1H11a1 1 0 0 0-1 1v1a2 2 0 1 1-4 0V5a2 2 0 1 0-4 0v2a1 1 0 0 0 1 1h3"/>',
  'alert-triangle':
    '<path d="M10.3 3.9L1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>',
} as const;

export type UiIconName = keyof typeof UI_ICON_PATHS;
export type WorkspaceIconName = keyof typeof WORKSPACE_ICON_PATHS;
export type IconName = UiIconName | WorkspaceIconName;

export function iconPaths(name: IconName): string | undefined {
  if (name in UI_ICON_PATHS) return UI_ICON_PATHS[name as UiIconName];
  return (WORKSPACE_ICON_PATHS as Record<string, { paths: string } | undefined>)[name]?.paths;
}
