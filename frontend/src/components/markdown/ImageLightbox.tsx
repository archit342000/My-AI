import { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { Icon } from '../icons/Icon';
import { pushModal } from '../../lib/modal-stack';
import { lockScroll, unlockScroll } from '../../lib/scroll-lock';

/**
 * Full-viewport image overlay. Portalled to body so no message ancestor can clip or offset it.
 * Closes on Escape (top of the modal stack), the close button or a click on the scrim, and locks
 * page scroll while open.
 */
export function ImageLightbox({ src, alt = '', onClose }: { src: string; alt?: string; onClose: () => void }) {
  const onCloseRef = useRef(onClose);
  useEffect(() => {
    onCloseRef.current = onClose;
  });

  useEffect(() => {
    const release = pushModal(() => onCloseRef.current());
    lockScroll();
    return () => {
      release();
      unlockScroll();
    };
  }, []);

  return createPortal(
    <div
      className="image-lightbox"
      role="dialog"
      aria-modal="true"
      aria-label="Image preview"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <button type="button" className="image-lightbox__close" aria-label="Close image" onClick={onClose}>
        <Icon name="close" size={20} strokeWidth={2.5} />
      </button>
      <img src={src} alt={alt} className="image-lightbox__img" />
    </div>,
    document.body,
  );
}
