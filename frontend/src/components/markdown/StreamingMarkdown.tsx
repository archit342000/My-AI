import { useMemo } from 'react';
import { splitBlocks } from '../../lib/markdown/blocks';
import { parseContent } from '../../lib/markdown/content';
import { StreamingBlock } from './StreamingBlock';

/**
 * Renders a reply that is still arriving block by block. Finished blocks keep their DOM (text
 * selection and "Copy" labels survive); only the block being written re-renders on each chunk.
 * The wrapper carries the reply's bubble classes once; a finished reply is rendered in one pass
 * with `Markdown`, so references across blocks resolve.
 */
export function StreamingMarkdown({ text }: { text: string }) {
  // Think tags are removed from the whole text first: a tag can span a blank line, which would
  // otherwise cut it in two blocks that each hide or show the wrong half.
  const blocks = useMemo(() => splitBlocks(parseContent(text).cleaned), [text]);
  return (
    <div className="message-content raw-text-content streaming-blocks">
      {blocks.map((block, i) => (
        <StreamingBlock key={i} text={block} />
      ))}
    </div>
  );
}
