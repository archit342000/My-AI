import '@testing-library/jest-dom/vitest';
import { beforeEach } from 'vitest';
import { initUserStorage } from '../lib/user-storage';
import { useAttachmentStore } from '../state/attachment-store';
import { useUserStore } from '../state/user-store';

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

// Components read the signed-in user and per-user storage keys. Tests run as the admin (which keeps the
// original localStorage key names) unless a test sets another user in its own beforeEach.

const TEST_ADMIN = { id: 'test-admin', email: 'admin@test', role: 'admin' } as const;
beforeEach(() => {
  initUserStorage(TEST_ADMIN);
  useUserStore.setState({ user: TEST_ADMIN, sessionExpired: false });
  // Staged files are kept per chat in a store: start every test with none.
  useAttachmentStore.setState({ lists: {}, doomed: {} });
});
