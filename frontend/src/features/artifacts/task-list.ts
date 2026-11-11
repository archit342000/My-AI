/** A task-list line: a list marker, then `[ ]` or `[x]`. */
const TASK = /^(\s*(?:[-*+]|\d+[.)])\s+\[)([ xX])(\])/;

/**
 * Ticks or unticks the nth task-list box (0-based, in reading order) of a markdown text. Lines inside
 * a fenced code block are not boxes. Returns the text unchanged when there is no such box.
 */
export function toggleTask(markdown: string, index: number): string {
  const lines = markdown.split('\n');
  let seen = 0;
  let fence: string | null = null;
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i] ?? '';
    const mark = /^\s*(```+|~~~+)/.exec(line)?.[1];
    if (mark) {
      if (fence === null) fence = mark[0] ?? null;
      else if (mark[0] === fence) fence = null;
      continue;
    }
    if (fence !== null) continue;
    const hit = TASK.exec(line);
    if (!hit) continue;
    if (seen === index) {
      lines[i] = line.replace(
        TASK,
        (_, before: string, state: string, after: string) =>
          `${before}${state === ' ' ? 'x' : ' '}${after}`,
      );
      return lines.join('\n');
    }
    seen += 1;
  }
  return markdown;
}
