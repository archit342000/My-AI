import { useEffect, useState, type RefObject } from 'react';

/** The files a drag or a paste carries (none for text or links). */
export function filesIn(data: DataTransfer | null): File[] {
  return data ? Array.from(data.files) : [];
}

function carriesFiles(data: DataTransfer | null): boolean {
  return Boolean(data && Array.from(data.types).includes('Files'));
}

/**
 * Accepts files dropped anywhere on the page area that holds `anchor` (its closest `<main>`). `dragging` is
 * true while a drag that carries files is over it, for a visible drop state. Nested elements fire their own
 * enter and leave events, so entries are counted.
 */
export function useFileDrop(
  anchor: RefObject<HTMLElement | null>,
  onFiles: (files: File[]) => void,
): { dragging: boolean } {
  const [dragging, setDragging] = useState(false);

  useEffect(() => {
    const zone = anchor.current?.closest('main');
    if (!zone) return undefined;
    let depth = 0;
    const enter = (e: Event) => {
      if (!carriesFiles((e as DragEvent).dataTransfer)) return;
      e.preventDefault();
      depth += 1;
      setDragging(true);
    };
    const over = (e: Event) => {
      if (!carriesFiles((e as DragEvent).dataTransfer)) return;
      e.preventDefault(); // allows the drop
    };
    const leave = (e: Event) => {
      if (!carriesFiles((e as DragEvent).dataTransfer)) return;
      depth = Math.max(0, depth - 1);
      if (depth === 0) setDragging(false);
    };
    const drop = (e: Event) => {
      const data = (e as DragEvent).dataTransfer;
      if (!carriesFiles(data)) return;
      e.preventDefault();
      depth = 0;
      setDragging(false);
      onFiles(filesIn(data));
    };
    // A drag that is cancelled (Escape) or ends outside the zone never fires leave here: reset on the window.
    const reset = () => {
      depth = 0;
      setDragging(false);
    };
    window.addEventListener('dragend', reset);
    window.addEventListener('drop', reset);
    zone.addEventListener('dragenter', enter);
    zone.addEventListener('dragover', over);
    zone.addEventListener('dragleave', leave);
    zone.addEventListener('drop', drop);
    return () => {
      zone.removeEventListener('dragenter', enter);
      zone.removeEventListener('dragover', over);
      zone.removeEventListener('dragleave', leave);
      zone.removeEventListener('drop', drop);
      window.removeEventListener('dragend', reset);
      window.removeEventListener('drop', reset);
    };
  }, [anchor, onFiles]);

  return { dragging };
}
