import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import type { ScopeRef } from '../../api/filesystem';
import { Icon } from '../../components/icons/Icon';
import { Button, IconButton } from '../../components/ui/Button';
import { useBackLayer } from '../../hooks/useBackLayer';
import { FileBrowser, type FileBrowserHandle } from './FileBrowser';

export interface ArtifactPanelProps {
  scope: ScopeRef;
  /** Shows the "Files" heading with a close button. Omit where the page gives its own heading. */
  onClose?: () => void;
}

/**
 * Hosts the file browser for a chat or a workspace, and lifts it out to fill the window on request.
 * The browser itself is never rebuilt when it moves: the open file, its undo history, the scroll
 * positions and the panel's width are as they were on the way back.
 */
export function ArtifactPanel({ scope, onClose }: ArtifactPanelProps) {
  const [full, setFull] = useState(false);
  // The browser lives in this box; the box is moved between the panel and the full-screen layer.
  const [box] = useState(() => {
    const el = document.createElement('div');
    el.className = 'fb-host';
    return el;
  });
  const inline = useRef<HTMLDivElement>(null);
  const lifted = useRef<HTMLDivElement>(null);
  const back = useRef<HTMLButtonElement>(null);
  const browser = useRef<FileBrowserHandle>(null);

  /** How far each scrolling part of the browser was scrolled, noted before it moves. */
  const scrolled = useRef<Array<readonly [HTMLElement, number, number]>>([]);

  /** Enters or leaves full screen. Scroll positions are read now: a moved element forgets them. */
  function setFullScreen(next: boolean) {
    scrolled.current = Array.from(
      box.querySelectorAll<HTMLElement>('.cm-scroller, [data-keep-scroll], .fb-files'),
    ).map((el) => [el, el.scrollTop, el.scrollLeft] as const);
    setFull(next);
  }

  useLayoutEffect(() => {
    const target = full ? lifted.current : inline.current;
    if (!target || box.parentNode === target) return;
    target.appendChild(box);
    const positions = scrolled.current;
    scrolled.current = [];
    const restore = () => {
      for (const [el, top, left] of positions) {
        el.scrollTop = top;
        el.scrollLeft = left;
      }
    };
    restore();
    // The editor measures itself again at its new size and may nudge the position: set it once more after that.
    const frame = requestAnimationFrame(() => requestAnimationFrame(restore));
    return () => cancelAnimationFrame(frame);
  }, [full, box]);

  useEffect(() => {
    if (full) back.current?.focus();
  }, [full]);

  // On a phone, Back leaves full screen first.
  useBackLayer(full, () => setFullScreen(false));

  async function close() {
    // Nothing typed is lost: it is saved first, and the panel stays if that fails.
    if ((await browser.current?.flush()) === false) return;
    onClose?.();
  }

  return (
    <div className="artifact-panel">
      {onClose ? (
        <header className="artifact-panel__header">
          <h2 className="artifact-panel__title">Files</h2>
          <IconButton
            icon="close"
            label="Close files"
            tooltip={false}
            onClick={() => void close()}
          />
        </header>
      ) : null}
      <div ref={inline} className="artifact-panel__body" />
      {full
        ? createPortal(
            <div
              className="files-full"
              role="dialog"
              aria-modal="true"
              aria-label="Files, full screen"
              onKeyDown={(e) => {
                // Escape first closes whatever is open on top (a menu, a pop-up); then it leaves full screen.
                if (
                  e.key === 'Escape' &&
                  !e.defaultPrevented &&
                  !document.querySelector('.ui-popover')
                ) {
                  setFullScreen(false);
                }
              }}
            >
              <header className="files-full__head">
                <Button ref={back} variant="ghost" onClick={() => setFullScreen(false)}>
                  <Icon name="chevron-left" size={16} />
                  Back
                </Button>
                <h2 className="files-full__title">Files</h2>
              </header>
              <div ref={lifted} className="files-full__body" />
            </div>,
            document.body,
          )
        : null}
      {createPortal(
        <FileBrowser
          ref={browser}
          scope={scope}
          full={full}
          onToggleFull={() => setFullScreen(!full)}
        />,
        box,
      )}
    </div>
  );
}
