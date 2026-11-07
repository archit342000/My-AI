import type { SVGProps } from 'react';
import { iconPaths, type IconName } from './icon-paths';
export type { IconName, UiIconName, WorkspaceIconName } from './icon-paths';
export { UI_ICON_PATHS } from './icon-paths';

export interface IconProps extends Omit<SVGProps<SVGSVGElement>, 'name'> {
  name: IconName;
  size?: number;
  strokeWidth?: number;
}

/**
 * Stroke icon. Paths come from our own static registry (never user input), so injecting the
 * markup is safe; the registry is the same markup the legacy UI used.
 */
export function Icon({ name, size = 18, strokeWidth = 2, ...rest }: IconProps) {
  const paths = iconPaths(name) ?? '';
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      dangerouslySetInnerHTML={{ __html: paths }}
      {...rest}
    />
  );
}
