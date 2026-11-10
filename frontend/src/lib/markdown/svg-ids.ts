const ID_LIST_ATTRS = new Set(['aria-labelledby', 'aria-describedby', 'aria-controls']);

/**
 * Gives every element id in an SVG a prefix and rewrites what points at it (`url(#id)`, `#id` in
 * attributes and in style text, id lists in `aria-labelledby`), so a clone of a rendered diagram can
 * live in the document next to the original without duplicate ids.
 */
export function prefixSvgIds(root: Element, prefix: string): void {
  const withIds = [root, ...Array.from(root.querySelectorAll('[id]'))].filter((el) => el.id !== '');
  if (withIds.length === 0) return;
  const ids = withIds.map((el) => el.id);
  const rewrite = (value: string) =>
    ids.reduce(
      (out, id) =>
        out.replace(
          new RegExp(`#${id.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}(?![\\w-])`, 'g'),
          `#${prefix}${id}`,
        ),
      value,
    );
  for (const el of [root, ...Array.from(root.querySelectorAll('*'))]) {
    for (const attr of Array.from(el.attributes)) {
      if (attr.name === 'id') continue;
      if (ID_LIST_ATTRS.has(attr.name)) {
        // These hold space-separated ids without a leading '#'.
        el.setAttribute(
          attr.name,
          attr.value
            .split(/\s+/)
            .map((token) => (ids.includes(token) ? `${prefix}${token}` : token))
            .join(' '),
        );
      } else if (attr.value.includes('#')) {
        el.setAttribute(attr.name, rewrite(attr.value));
      }
    }
    if (el.tagName.toLowerCase() === 'style' && el.textContent)
      el.textContent = rewrite(el.textContent);
  }
  for (const el of withIds) el.id = `${prefix}${el.id}`;
}
