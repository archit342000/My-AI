import { useRef, useState, type CSSProperties, type KeyboardEvent, type PointerEvent } from 'react';
import { createPortal } from 'react-dom';
import type { ScopeRef } from '../../api/filesystem';
import { useUiStore } from '../../state/ui-store';
import { ArtifactPanel } from './ArtifactPanel';

const WIDTH_KEY = 'my_ai_artifact_width';
const MIN_WIDTH = 320;
const DEFAULT_WIDTH = 400;
const KEY_STEP = 16;
/** Gaps of the app frame around the panels (the frame's padding and the space between panels). */
const EDGE_GAP = 16;

/** Room the chat keeps beside the panel. */
const MIN_CHAT_WIDTH = 360;

function maxWidth(): number {
  // The navigation panel takes its own room (a rail or the full panel; on a phone it is a drawer on top).
  const nav = document.getElementById('sidebar');
  const navWidth =
    nav && getComputedStyle(nav).position !== 'fixed' ? nav.getBoundingClientRect().width : 0;
  const room = window.innerWidth - navWidth - MIN_CHAT_WIDTH - EDGE_GAP * 4;
  return Math.max(MIN_WIDTH, Math.min(960, room));
}

function clamp(width: number): number {
  return Math.min(maxWidth(), Math.max(MIN_WIDTH, Math.round(width)));
}

/** The stored width, or the default. Storage can be blocked, so every access is guarded. */
function readWidth(): number {
  try {
    const stored = Number(window.localStorage.getItem(WIDTH_KEY));
    if (Number.isFinite(stored) && stored >= MIN_WIDTH) return clamp(stored);
  } catch {
    // Storage unavailable (private mode or blocked): fall back to the default.
  }
  return DEFAULT_WIDTH;
}

function persistWidth(width: number): void {
  try {
    window.localStorage.setItem(WIDTH_KEY, String(width));
  } catch {
    // Not persisted; the width still applies for this visit.
  }
}

/** Right-hand files overlay in a chat. Resizable on desktop (drag or arrow keys); a full-screen sheet on phones. */
export function ArtifactDrawer({ scope }: { scope: ScopeRef }) {
  const setOpen = useUiStore((s) => s.setArtifactsOpen);
  const [width, setWidth] = useState(readWidth);
  const drag = useRef<{ startX: number; startWidth: number } | null>(null);

  function onPointerDown(event: PointerEvent<HTMLDivElement>) {
    drag.current = { startX: event.clientX, startWidth: width };
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function onPointerMove(event: PointerEvent<HTMLDivElement>) {
    const start = drag.current;
    if (!start) return;
    setWidth(clamp(start.startWidth + (start.startX - event.clientX)));
  }

  function endDrag() {
    if (!drag.current) return;
    drag.current = null;
    persistWidth(width);
  }

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
    event.preventDefault();
    const next = clamp(width + (event.key === 'ArrowLeft' ? KEY_STEP : -KEY_STEP));
    setWidth(next);
    persistWidth(next);
  }

  const style = { '--artifact-width': `${width}px` } as CSSProperties;

  const frame = document.getElementById('app-root');
  const drawer = (
    <aside
      className="artifact-drawer"
      style={style} // dynamic-style
      aria-label="Files"
    >
      <div
        className="artifact-drawer__handle"
        role="separator"
        aria-orientation="vertical"
        aria-label="Drag to resize the files panel"
        aria-valuemin={MIN_WIDTH}
        aria-valuemax={maxWidth()}
        aria-valuenow={width}
        tabIndex={0}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
        onKeyDown={onKeyDown}
      />
      <ArtifactPanel scope={scope} onClose={() => setOpen(false)} />
    </aside>
  );
  // Beside the content panel, as a third panel of the app frame (a full screen of its own on a phone).
  return frame ? createPortal(drawer, frame) : drawer;
}
