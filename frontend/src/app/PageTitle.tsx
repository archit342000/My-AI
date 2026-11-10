import { useContext, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { PageTitleSlot } from './page-header-context';

/**
 * The title of the current page, shown in the app header (rule book 5.3). A page renders this
 * once; the text (or a control such as the rename field) appears in the header's title place.
 */
export function PageTitle({ children }: { children: ReactNode }) {
  const slot = useContext(PageTitleSlot);
  if (slot === undefined) return <div className="main-title">{children}</div>;
  return slot ? createPortal(children, slot) : null;
}
