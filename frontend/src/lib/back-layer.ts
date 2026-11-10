import { isPhoneWidth } from './breakpoints';

/**
 * Back on a phone undoes the newest layer first (rule book Part 6): a pop-up, a menu, the drawer, a
 * side panel, a full-screen page. Layers that are not addresses of their own register here. While
 * any is open there is one extra step in the browser's history; Back lands on it, the newest layer
 * closes, and the step is put back while more layers remain.
 */
interface Layer {
  /** Closes the layer. For a layer that cannot be skipped, says so instead. */
  onBack: () => void;
  /** A whole-screen wait: Back does not close it. */
  sticky: boolean;
}

const layers: Layer[] = [];
/** True while our extra step is the newest history entry. */
let armed = false;
/** Our own `history.back()` is on its way: its popstate is not the person pressing Back. */
let undoing = false;
let scheduled = false;
let listening = false;

const MARK = 'backLayer';

function isOurStep(): boolean {
  const state = window.history.state as Record<string, unknown> | null;
  return Boolean(state && state[MARK]);
}

/** Brings the history in line with whether a layer is open. Runs once after the current work. */
function sync(): void {
  scheduled = false;
  if (undoing) return; // the popstate of our own step back runs sync again
  const wanted = layers.length > 0;
  if (wanted && !armed) {
    // Same address, and the router's own values kept, so the router sees nothing to do.
    window.history.pushState({ ...(window.history.state as object | null), [MARK]: true }, '');
    armed = true;
  } else if (!wanted && armed) {
    armed = false;
    // Only step back over our own step: after a move to another page it lies further down and stays.
    if (isOurStep()) {
      undoing = true;
      window.history.back();
    }
  }
}

function schedule(): void {
  if (scheduled) return;
  scheduled = true;
  queueMicrotask(sync);
}

function onPopState(): void {
  if (undoing) {
    undoing = false;
    schedule();
    return;
  }
  if (!armed) return;
  // The person pressed Back: our step is gone, and the newest layer answers.
  armed = false;
  const top = layers[layers.length - 1];
  if (!top) return;
  if (!top.sticky) layers.pop();
  top.onBack();
  schedule();
}

/**
 * Registers an open layer. Returns what to call when the layer closes by itself (a button, Escape).
 * Does nothing on wider screens, where Back keeps its usual meaning.
 */
export function pushBackLayer(onBack: () => void, options: { sticky?: boolean } = {}): () => void {
  if (typeof window === 'undefined' || !isPhoneWidth()) return () => undefined;
  if (!listening) {
    window.addEventListener('popstate', onPopState);
    listening = true;
  }
  const layer: Layer = { onBack, sticky: options.sticky ?? false };
  layers.push(layer);
  schedule();
  return () => {
    const at = layers.indexOf(layer);
    if (at === -1) return; // Back already closed it
    layers.splice(at, 1);
    schedule();
  };
}

/** How many layers Back would close before it moves between pages. */
export function backLayerDepth(): number {
  return layers.length;
}

/** For tests: forget every layer and the state of the extra step. */
export function resetBackLayers(): void {
  layers.length = 0;
  armed = false;
  undoing = false;
  scheduled = false;
}
