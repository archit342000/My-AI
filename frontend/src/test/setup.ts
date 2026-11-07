import '@testing-library/jest-dom/vitest';

// jsdom does not implement layout scrolling; stub it so unlocking modals is quiet.
window.scrollTo = (() => undefined) as typeof window.scrollTo;
