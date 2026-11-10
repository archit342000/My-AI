import { useEffect, useRef } from 'react';
import { prefixSvgIds } from '../../lib/markdown/svg-ids';
import { Modal } from '../ui/Modal';

/**
 * Full view of a rendered mermaid diagram. The diagram is the already rendered (and sanitised)
 * SVG node from the transcript, cloned into the dialog; no new HTML source is introduced.
 */
export function MermaidDialog({ diagram, onClose }: { diagram: SVGElement; onClose: () => void }) {
  const host = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const clone = diagram.cloneNode(true) as SVGElement;
    prefixSvgIds(clone, 'popout-'); // the original stays in the transcript: no duplicate ids
    clone.removeAttribute('width');
    clone.removeAttribute('height');
    clone.style.maxWidth = '100%';
    clone.style.height = 'auto';
    host.current?.replaceChildren(clone);
  }, [diagram]);
  return (
    <Modal open onClose={onClose} title="Diagram" maxWidth="min(96vw, 1200px)">
      <div ref={host} className="mermaid-popout" />
    </Modal>
  );
}
