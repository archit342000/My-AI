/**
 * The fade behind words that sit on the dot sphere (rule book 3.3): one soft patch of the page
 * colour behind each line of words and each button, and nothing behind the gaps.
 */

export interface Box {
  left: number;
  top: number;
  width: number;
  height: number;
}

/** How far a patch reaches past its words: grows with the lettering, within fixed limits. */
export function fadePadding(height: number): { x: number; y: number } {
  return {
    x: Math.min(14, Math.max(8, height * 0.14)),
    y: Math.min(8, Math.max(4, height * 0.06)),
  };
}

/**
 * Turns the measured boxes of lines and buttons (page coordinates) into patches placed relative
 * to their container's corner. Empty boxes are dropped.
 */
export function fadePatches(boxes: Box[], origin: { left: number; top: number }): Box[] {
  const patches: Box[] = [];
  for (const box of boxes) {
    if (!box.width || !box.height) continue;
    const pad = fadePadding(box.height);
    patches.push({
      left: Math.round(box.left - origin.left - pad.x),
      top: Math.round(box.top - origin.top - pad.y),
      width: Math.round(box.width + pad.x * 2),
      height: Math.round(box.height + pad.y * 2),
    });
  }
  return patches;
}

/** Measures every line of text and every button or status light inside `element`. */
export function measureWords(element: HTMLElement): Box[] {
  const boxes: Box[] = [];
  const range = document.createRange();
  const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    if (!node.nodeValue?.trim()) continue;
    // The patches themselves hold no text, but skip the layer in case that ever changes.
    if (node.parentElement?.closest('.fade-layer')) continue;
    range.selectNodeContents(node);
    // getClientRects is missing in some test environments.
    const rects = typeof range.getClientRects === 'function' ? range.getClientRects() : [];
    for (const rect of Array.from(rects)) boxes.push(rect);
  }
  // Buttons, the status light and a dead end's small drawing are shapes, not text: each gets its own patch.
  for (const control of Array.from(element.querySelectorAll('button, a, .led, .dotted-drawing'))) {
    boxes.push(control.getBoundingClientRect());
  }
  return boxes;
}
