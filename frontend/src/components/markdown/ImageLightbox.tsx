import { Viewer } from '../ui/Viewer';

/**
 * A picture from an answer in the bigger view: a window with zoom. Closes on Escape (top of the
 * modal stack), the close button or a press outside, and locks page scroll while open.
 */
export function ImageLightbox({
  src,
  alt = '',
  onClose,
}: {
  src: string;
  alt?: string;
  onClose: () => void;
}) {
  return (
    <Viewer open onClose={onClose} title={alt || 'Picture'}>
      <img src={src} alt={alt} className="image-lightbox__img" />
    </Viewer>
  );
}
