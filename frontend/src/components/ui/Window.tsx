import type { ReactNode, RefObject } from 'react';
import { Modal } from './Modal';

export interface WindowProps {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  /** Shown beside the title: a status light, a count. */
  status?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  onBack?: () => void;
  maxWidth?: number | string;
  id?: string;
  initialFocusRef?: RefObject<HTMLElement | null>;
}

/**
 * The large window (rule book 7.11): a tool or a bigger view that opens over the app, with a
 * title, an optional status and Close. Fills the screen on a phone, where Back closes it.
 */
export function Window({ maxWidth = 'min(72rem, 100%)', ...rest }: WindowProps) {
  return <Modal {...rest} maxWidth={maxWidth} variant="window" />;
}
