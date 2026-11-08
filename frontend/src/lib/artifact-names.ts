/**
 * Default title for a new artifact (D2): `Untitled` when no loaded title is exactly `Untitled`,
 * otherwise `Untitled N` with the lowest N >= 2 not already used.
 */
export function nextArtifactTitle(existingTitles: readonly string[]): string {
  const taken = new Set(existingTitles);
  if (!taken.has('Untitled')) return 'Untitled';
  let n = 2;
  while (taken.has(`Untitled ${n}`)) n += 1;
  return `Untitled ${n}`;
}
