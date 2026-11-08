import { Icon, type UiIconName } from '../icons/Icon';
import { cx } from '../../lib/cx';
import { IconButton } from './Button';
import { useToastStore, type ToastType } from './toast-store';

const ICON_FOR: Record<ToastType, UiIconName> = { info: 'info', success: 'success', error: 'error' };
const VARIANT_CLASS: Record<ToastType, string> = {
  info: 'ui-toast--info',
  success: 'ui-toast--success',
  error: 'ui-toast--error',
};

/** Renders the active toasts as a stack. Errors are announced as alerts and stay until dismissed. */
export function ToastViewport() {
  const toasts = useToastStore((s) => s.toasts);
  const dismiss = useToastStore((s) => s.dismiss);
  return (
    <div className="ui-toast-viewport">
      {toasts.map((t) => (
        <div
          key={t.id}
          role={t.type === 'error' ? 'alert' : 'status'}
          className={cx('ui-toast', VARIANT_CLASS[t.type], t.leaving && 'ui-toast--leaving')}
        >
          <span className="ui-toast__icon" aria-hidden="true">
            <Icon name={ICON_FOR[t.type]} size={16} />
          </span>
          <span className="ui-toast__message">{t.message}</span>
          <IconButton
            icon="close"
            label="Dismiss notification"
            size="sm"
            className="ui-toast__dismiss"
            onClick={() => dismiss(t.id)}
          />
        </div>
      ))}
    </div>
  );
}
