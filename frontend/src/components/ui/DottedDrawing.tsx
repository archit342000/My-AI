export type DrawingName = 'nothing' | 'not-found' | 'offline' | 'broke' | 'gone';

const DASH = '0.1 3.4';

/** The small dotted drawings of empty screens and dead ends (rule book 7.12, 7.13). Decoration only. */
export function DottedDrawing({ name, size = 56 }: { name: DrawingName; size?: number }) {
  return (
    <svg
      className="dotted-drawing"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.7}
      strokeLinecap="round"
      aria-hidden="true"
    >
      {name === 'nothing' ? (
        <>
          <circle cx="12" cy="12" r="9" strokeDasharray={DASH} />
          <circle cx="12" cy="12" r="4.6" strokeDasharray={DASH} />
          <circle cx="12" cy="12" r="0.5" />
        </>
      ) : name === 'not-found' ? (
        <>
          <circle cx="10.5" cy="10.5" r="6.5" strokeDasharray={DASH} />
          <path d="M15.5 15.5l5 5" strokeDasharray={DASH} />
        </>
      ) : name === 'offline' ? (
        <>
          <path
            d="M7 18.5h10.5a4 4 0 0 0 .6-7.95A6 6 0 0 0 6.5 9.5 4.5 4.5 0 0 0 7 18.5z"
            strokeDasharray={DASH}
          />
          <path d="M4 4l16 16" />
        </>
      ) : name === 'broke' ? (
        <>
          <path d="M12 3.5l9.5 16.5h-19z" strokeDasharray={DASH} />
          <path d="M12 10v4.5M12 17.2h.01" strokeWidth={2} />
        </>
      ) : (
        <>
          <path d="M4 8.5l8-4.5 8 4.5v7l-8 4.5-8-4.500z" strokeDasharray={DASH} />
          <path d="M4 8.5l8 4.5 8-4.5M12 13v7" strokeDasharray={DASH} />
        </>
      )}
    </svg>
  );
}
