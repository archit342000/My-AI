import { memo } from 'react';
import { Markdown } from './Markdown';

/** One finished markdown block of a streaming reply; unchanged text skips re-rendering. */
export const StreamingBlock = memo(function StreamingBlock({ text }: { text: string }) {
  return <Markdown text={text} className="streaming-block" />;
});
