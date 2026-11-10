import { useState } from 'react';

/** Results longer than this are clipped until the user asks for the rest. */
const CLIP_CHARS = 1500;

/** Text in a `<pre>`, clipped to CLIP_CHARS with a "Show more" toggle. */
export function ClippedText({ text, label }: { text: string; label: string }) {
  const [full, setFull] = useState(false);
  const long = text.length > CLIP_CHARS;
  const shown = long && !full ? `${text.slice(0, CLIP_CHARS)}\n…` : text;
  return (
    <div className="activity-content" role="group" aria-label={label}>
      <pre className="font-mono">{shown}</pre>
      {long ? (
        <button type="button" className="activity-more" onClick={() => setFull((value) => !value)}>
          {full ? 'Show less' : `Show more (${Math.ceil(text.length / 1024)} KB)`}
        </button>
      ) : null}
    </div>
  );
}
