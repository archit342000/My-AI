import { useEffect, useMemo, useRef, useState, type MouseEvent } from 'react';
import { renderMarkdown } from '../../lib/markdown/renderer';
import { showToast } from '../ui/toast-store';
import { useUiStore } from '../../state/ui-store';
import { ImageLightbox } from './ImageLightbox';
import { MermaidDialog } from './MermaidDialog';

/**
 * Renders markdown as sanitised HTML and attaches the interactive pieces the legacy UI had:
 * copy buttons on code blocks, mermaid diagrams with zoom controls, and an image lightbox.
 */
export function Markdown({ text, className = 'message-content raw-text-content' }: { text: string; className?: string }) {
  const html = useMemo(() => renderMarkdown(text), [text]);
  const ref = useRef<HTMLDivElement>(null);
  const [lightbox, setLightbox] = useState<string | null>(null);
  const [diagram, setDiagram] = useState<SVGElement | null>(null);

  useEffect(() => {
    const root = ref.current;
    if (!root || !root.querySelector('pre.mermaid')) return undefined;
    let cancelled = false;
    void import('mermaid').then(async ({ default: mermaid }) => {
      if (cancelled) return;
      mermaid.initialize({ startOnLoad: false, theme: document.documentElement.classList.contains('dark') ? 'dark' : 'default' });
      const nodes = Array.from(root.querySelectorAll<HTMLElement>('pre.mermaid'));
      try {
        await mermaid.run({ nodes });
      } catch (err) {
        console.warn('Mermaid rendering failed', err);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [html]);

  function onClick(event: MouseEvent<HTMLDivElement>) {
    const target = event.target as HTMLElement;
    const copy = target.closest<HTMLElement>('.copy-code-btn');
    if (copy) {
      const code = decodeURIComponent(copy.dataset.code ?? '');
      void navigator.clipboard?.writeText(code);
      const label = copy.querySelector('span');
      if (label) {
        label.textContent = 'Copied';
        window.setTimeout(() => (label.textContent = 'Copy'), 1500);
      }
      return;
    }
    const fileLink = target.closest<HTMLAnchorElement>('a.file-link');
    if (fileLink) {
      event.preventDefault();
      const path = fileLink.dataset.path ?? '';
      if (useUiStore.getState().filesAvailable) useUiStore.getState().openArtifact(path);
      else showToast('Open the chat to view its files', 'info');
      return;
    }
    const zoom = target.closest<HTMLElement>('.mermaid-ctrl-btn');
    if (zoom) {
      const container = zoom.closest<HTMLElement>('.mermaid-wrapper-container');
      const pre = container?.querySelector<HTMLElement>('pre.mermaid');
      if (zoom.classList.contains('zoom-popout-btn')) {
        const svg = pre?.querySelector('svg');
        if (svg) setDiagram(svg);
        else showToast('The diagram is still rendering', 'info');
      } else if (pre) {
        applyZoom(pre, zoom);
      }
      return;
    }
    const img = target.closest<HTMLImageElement>('img.lightbox-img');
    if (img?.src) setLightbox(img.src);
  }

  return (
    <>
      <div ref={ref} className={className} onClick={onClick} dangerouslySetInnerHTML={{ __html: html }} />
      {lightbox ? <ImageLightbox src={lightbox} onClose={() => setLightbox(null)} /> : null}
      {diagram ? <MermaidDialog diagram={diagram} onClose={() => setDiagram(null)} /> : null}
    </>
  );
}

/** Zoom state lives on the element (`data-scale`) so it survives re-renders of the markdown HTML. */
function applyZoom(pre: HTMLElement, control: HTMLElement) {
  const current = Number(pre.dataset.scale ?? '1');
  let next = current;
  if (control.classList.contains('zoom-in-btn')) next = Math.min(current + 0.15, 4);
  else if (control.classList.contains('zoom-out-btn')) next = Math.max(current - 0.15, 0.1);
  else if (control.classList.contains('zoom-reset-btn')) next = 1;
  else return;
  pre.dataset.scale = String(next);
  pre.style.transform = `scale(${next})`;
}
