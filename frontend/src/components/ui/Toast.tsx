import { Icon, type UiIconName } from '../icons/Icon';
import { useToastStore, type ToastType } from './toast-store';

const ICON_FOR: Record<ToastType, UiIconName> = { info: 'info', success: 'success', error: 'error' };

/** Renders the active toasts. Mount once near the root. */
export function ToastViewport() {
  const toasts = useToastStore((s) => s.toasts);
  return (
    <div role="status" aria-live="polite">
      {toasts.map((t) => (
        <div key={t.id} className={`toast-notification${t.leaving ? '' : ' show'}`}>
          <Icon name={ICON_FOR[t.type]} size={16} />
          <span>{t.message}</span>
        </div>
      ))}
    </div>
  );
}
