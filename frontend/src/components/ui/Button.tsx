import type { ButtonHTMLAttributes } from 'react';
import { Icon, type IconName } from '../icons/Icon';
import { cx } from '../../lib/cx';
import { Tooltip } from './Tooltip';

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: 'md' | 'sm';
  /** Disables the button and shows a spinner (sets aria-busy). */
  loading?: boolean;
}

const VARIANT_CLASS: Record<ButtonVariant, string> = {
  primary: 'ui-button--primary',
  secondary: 'ui-button--secondary',
  ghost: 'ui-button--ghost',
  danger: 'ui-button--danger',
};

const SIZE_CLASS: Record<'md' | 'sm', string | undefined> = {
  md: undefined,
  sm: 'ui-button--sm',
};

export function Button({
  variant = 'secondary',
  size = 'md',
  loading = false,
  disabled,
  type = 'button',
  className,
  children,
  ...rest
}: ButtonProps) {
  return (
    <button
      {...rest}
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cx('ui-button', VARIANT_CLASS[variant], SIZE_CLASS[size], className)}
    >
      {loading ? <span className="ui-spinner" aria-hidden="true" /> : null}
      {children}
    </button>
  );
}

export interface IconButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'children'> {
  icon: IconName;
  /** Accessible name; also the tooltip text unless `tooltip` is false. */
  label: string;
  size?: 'md' | 'sm';
  tone?: 'default' | 'danger';
  tooltip?: boolean;
}

const ICON_SIZE_CLASS: Record<'md' | 'sm', string | undefined> = {
  md: undefined,
  sm: 'ui-icon-button--sm',
};

const TONE_CLASS: Record<'default' | 'danger', string | undefined> = {
  default: undefined,
  danger: 'ui-icon-button--danger',
};

export function IconButton({
  icon,
  label,
  size = 'md',
  tone = 'default',
  tooltip = true,
  type = 'button',
  className,
  ...rest
}: IconButtonProps) {
  const button = (
    <button
      {...rest}
      type={type}
      aria-label={label}
      className={cx('ui-icon-button', ICON_SIZE_CLASS[size], TONE_CLASS[tone], className)}
    >
      <Icon name={icon} size={size === 'sm' ? 14 : 16} />
    </button>
  );
  return tooltip ? <Tooltip content={label}>{button}</Tooltip> : button;
}
