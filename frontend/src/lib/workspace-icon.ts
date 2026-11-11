import { iconPaths, type IconName } from '../components/icons/icon-paths';

/** The icon a workspace has when none was chosen. */
export const DEFAULT_WORKSPACE_ICON: IconName = 'folder';

/** A workspace's own icon, or the folder when it is unset or no longer known. */
export function workspaceIconName(icon: string | null | undefined): IconName {
  return icon && iconPaths(icon as IconName) ? (icon as IconName) : DEFAULT_WORKSPACE_ICON;
}

/**
 * Workspaces made in the old app may carry an emoji in place of an icon name: it is shown as it is.
 * Null when the workspace has a known icon or none.
 */
export function workspaceEmoji(icon: string | null | undefined): string | null {
  return icon && !iconPaths(icon as IconName) ? icon : null;
}
