import '@testing-library/jest-dom/vitest';

// jsdom does not implement layout scrolling; stub it so unlocking modals is quiet.
window.scrollTo = (() => undefined) as typeof window.scrollTo;

// jsdom lacks matchMedia and element scrolling; the composer and auto-scroller call them.
if (!window.matchMedia) {
  window.matchMedia = ((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => undefined,
    removeListener: () => undefined,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia;
}
if (!Element.prototype.scrollTo) {
  Element.prototype.scrollTo = (() => undefined) as unknown as typeof Element.prototype.scrollTo;
}
