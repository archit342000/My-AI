import type { ReactNode } from 'react';

/** A small grey word that describes a thing (a kind, a language). Not pressable. */
export function Tag({ children }: { children: ReactNode }) {
  return <span className="ui-tag">{children}</span>;
}
