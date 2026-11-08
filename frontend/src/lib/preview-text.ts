/**
 * Plain-text preview of a markdown snippet: markup is removed and only the first sentence is kept
 * (plan F-29). Used by list rows, where raw `# ROLE` headings or code fences read as noise.
 */
export function firstSentencePreview(markdown: string): string {
  const plain = markdown
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/`([^`]*)`/g, '$1')
    .replace(/!\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')
    .replace(/<[^>]+>/g, ' ')
    .replace(/^\s{0,3}#{1,6}\s+/gm, '')
    .replace(/^\s{0,3}>\s?/gm, '')
    .replace(/^\s*(?:[-*+]|\d+\.)\s+/gm, '')
    .replace(/(\*\*|__|\*|_)(.+?)\1/g, '$2')
    .replace(/\s+/g, ' ')
    .trim();
  if (!plain) return '';
  const match = /^(.+?[.!?])(\s|$)/.exec(plain);
  return match ? match[1]! : plain;
}
