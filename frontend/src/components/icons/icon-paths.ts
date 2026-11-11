import { WORKSPACE_ICON_PATHS } from './workspace-icons.generated';

/**
 * Named icon keys. The app's own icons follow the design system's starting set (rule book 2.6:
 * outlines, 2px line on a 24 grid, rounded ends); the workspace registry adds the icons a workspace can be given.
 */
export const UI_ICON_PATHS = {
  close: '<path d="M6 6l12 12M18 6L6 18"/>',
  menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
  'chevron-left': '<path d="M15 6l-6 6 6 6" stroke-linecap="round" stroke-linejoin="round"/>',
  'chevron-right': '<path d="M9 6l6 6-6 6"/>',
  'chevron-down': '<path d="M6 9l6 6 6-6" stroke-linecap="round" stroke-linejoin="round"/>',
  plus: '<path d="M12 5v14M5 12h14" stroke-linecap="round" stroke-linejoin="round"/>',
  'grid-plus':
    '<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><line x1="17.5" y1="14" x2="17.5" y2="21"/><line x1="14" y1="17.5" x2="21" y2="17.5"/>',
  logs: '<path d="M15 12h-5M15 8h-5M19 17V5a2 2 0 0 0-2-2H4"/><path d="M8 21h12a2 2 0 0 0 2-2v-1a1 1 0 0 0-1-1H11a1 1 0 0 0-1 1v1a2 2 0 1 1-4 0V5a2 2 0 1 0-4 0v2a1 1 0 0 0 1 1h3"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5.500M12 7.500h.01"/>',
  error:
    '<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>',
  success: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
  check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
  minus: '<path d="M6 12h12"/>',
  expand: '<path d="M9 4H4v5M15 4h5v5M9 20H4v-5M15 20h5v-5"/>',
  more: '<path d="M5 12h.01M12 12h.01M19 12h.01" stroke-width="3.4"/>',
  panel: '<rect x="3" y="4" width="18" height="16" rx="3"/><path d="M9 4v16"/>',
  sliders:
    '<path d="M4 6h8M18 6h2M4 12h2M12 12h8M4 18h10M20 18h0"/><circle cx="15" cy="6" r="2.2"/><circle cx="9" cy="12" r="2.2"/><circle cx="17" cy="18" r="2.2"/>',
  chip: '<rect x="6" y="6" width="12" height="12" rx="2.5"/><path d="M9.5 2.5V6M14.5 2.5V6M9.5 18v3.5M14.5 18v3.5M2.5 9.5H6M2.5 14.5H6M18 9.5h3.5M18 14.5h3.5"/>',
  list: '<path d="M9 6h11M9 12h11M9 18h11M4.5 6h.01M4.5 12h.01M4.5 18h.01"/>',
  page: '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/>',
  'temp-chat': '<circle cx="12" cy="12" r="9" stroke-dasharray="3 3.2"/><path d="M12 8v4l2.5 2"/>',
  'new-workspace':
    '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="M12 11v5M9.5 13.5h5"/>',
  undo: '<path d="M9 14L4 9l5-5"/><path d="M4 9h10a6 6 0 0 1 0 12h-3"/>',
  redo: '<path d="M15 14l5-5-5-5"/><path d="M20 9H10a6 6 0 0 0 0 12h3"/>',
  download: '<path d="M12 4v11M7 11l5 5 5-5M5 20h14"/>',
  copy: '<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V6a2 2 0 0 1 2-2h9"/>',
  'refresh-cw': '<path d="M20 12a8 8 0 1 1-2.6-5.900"/><path d="M20 4v5h-5"/>',
  'scroll-text':
    '<path d="M15 12h-5M15 8h-5M19 17V5a2 2 0 0 0-2-2H4"/><path d="M8 21h12a2 2 0 0 0 2-2v-1a1 1 0 0 0-1-1H11a1 1 0 0 0-1 1v1a2 2 0 1 1-4 0V5a2 2 0 1 0-4 0v2a1 1 0 0 0 1 1h3"/>',
  'alert-triangle': '<path d="M12 4l9 16H3z"/><path d="M12 10v4.500M12 17.500h.01"/>',
  // The design system's starting set (rule book 2.6): these names draw the same shapes as its reference page.
  send: '<path d="M12 19V5M5 12l7-7 7 7"/>',
  attach:
    '<path d="M20 11.5l-8.200 8.200a5 5 0 0 1-7.100-7.100l8.600-8.600a3.400 3.400 0 0 1 4.800 4.800l-8.500 8.500a1.800 1.800 0 0 1-2.500-2.500l7.800-7.800"/>',
  tool: '<path d="M14.500 6.500a4 4 0 0 0 5 5L11 20a2.100 2.100 0 0 1-3-3l8.500-8.500"/><path d="M14.500 6.500l2.200-2.200a4 4 0 0 0-5.200 5.200"/>',
  search: '<circle cx="11" cy="11" r="6.500"/><path d="M16 16l4.500 4.500"/>',
  edit: '<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="M13.500 6.500l4 4"/>',
  trash: '<path d="M4 7h16M9 7V4.500h6V7M6.500 7l1 13h9l1-13M10 11v5.500M14 11v5.500"/>',
  folder: '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
  file: '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/>',
  'file-text':
    '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7.500V12l3 2"/>',
  play: '<path d="M7.500 5l11 7-11 7z"/>',
  'message-square':
    '<path d="M5 5h14a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-7l-4.500 3.500V17H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2z"/>',
  user: '<circle cx="12" cy="8" r="3.600"/><path d="M4.500 20c1-3.600 4-5.400 7.500-5.400s6.500 1.800 7.500 5.400"/>',
  zap: '<path d="M13 3L5 13.500h6l-1 7.500 8-10.500h-6z"/>',
  bookmark: '<path d="M7 4h10a1 1 0 0 1 1 1v15l-6-4-6 4V5a1 1 0 0 1 1-1z"/>',
  nodes:
    '<circle cx="6" cy="6" r="2.400"/><circle cx="18" cy="6" r="2.400"/><circle cx="12" cy="18" r="2.400"/><path d="M7.600 8l3.200 7.800M16.400 8l-3.200 7.800M8.400 6h7.200"/>',
  picture:
    '<rect x="3" y="5" width="18" height="14" rx="2.500"/><circle cx="9" cy="10.500" r="1.600"/><path d="M4 17l5-4.500 3.500 3 3-2.500L20 17"/>',
} as const;

export type UiIconName = keyof typeof UI_ICON_PATHS;
export type WorkspaceIconName = keyof typeof WORKSPACE_ICON_PATHS;
export type IconName = UiIconName | WorkspaceIconName;

export function iconPaths(name: IconName): string | undefined {
  if (Object.hasOwn(UI_ICON_PATHS, name)) return UI_ICON_PATHS[name as UiIconName];
  if (!Object.hasOwn(WORKSPACE_ICON_PATHS, name)) return undefined;
  return (WORKSPACE_ICON_PATHS as Record<string, { paths: string } | undefined>)[name]?.paths;
}
