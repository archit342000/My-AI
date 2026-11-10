/** True when a line has an odd number of `$$` markers, so it opens or closes a math block. */
function oddDollars(line: string): boolean {
  return (line.split('$$').length - 1) % 2 === 1;
}

/**
 * Splits markdown at blank lines that are not inside a fenced code block or a `$$` math block.
 * Joining the pieces with "\n" gives the input back, so each piece can be rendered on its own while
 * a reply streams and only the last one changes. A blank line stays attached to the block it ends,
 * and no piece is blank (a blank-only piece joins its neighbour).
 */
export function splitBlocks(text: string): string[] {
  if (text.trim() === '') return [];
  const blocks: string[] = [];
  let current: string[] = [];
  let fence: string | null = null;
  let math = false;

  const flush = () => {
    if (current.length === 0) return;
    const piece = current.join('\n');
    current = [];
    const last = blocks.length - 1;
    if (piece.trim() === '' && last >= 0) blocks[last] = `${blocks[last] ?? ''}\n${piece}`;
    else blocks.push(piece);
  };

  const lines = text.split('\n');
  for (const [index, line] of lines.entries()) {
    const trimmed = line.trim();
    if (fence === null && !math) {
      const open = /^(`{3,}|~{3,})(.*)$/.exec(trimmed);
      // A backtick fence's info string cannot contain a backtick (that is inline code instead).
      if (open && !(open[1]?.startsWith('`') && open[2]?.includes('`'))) fence = open[1] ?? '```';
      else if (trimmed === '$$') math = true;
      // A `$$` that starts a line of text opens a block only if a later line closes it; a stray one
      // ("$$5 is the price") must not swallow the rest of the reply into one block.
      else if (
        trimmed.startsWith('$$') &&
        oddDollars(trimmed) &&
        lines.slice(index + 1).some((later) => later.includes('$$'))
      ) {
        math = true;
      }
    } else if (fence !== null) {
      if (trimmed.startsWith(fence) && /^(`+|~+)$/.test(trimmed)) fence = null;
    } else if (oddDollars(trimmed)) {
      math = false;
    }
    current.push(line);
    // The blank line belongs to the block it ends.
    if (trimmed === '' && fence === null && !math) {
      // Leading blank lines have no block to join yet: they ride along with the next one.
      if (blocks.length > 0 || current.some((l) => l.trim() !== '')) flush();
    }
  }
  flush();
  return blocks;
}
