import { createContext } from 'react';

/**
 * The element in the app header that the current page's title is rendered into.
 * `undefined`: there is no app header (a page rendered on its own, as in tests), so the title
 * is rendered in place. `null`: the header exists but is not mounted yet.
 */
export const PageTitleSlot = createContext<HTMLElement | null | undefined>(undefined);
