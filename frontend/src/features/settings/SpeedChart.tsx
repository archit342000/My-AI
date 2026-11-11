import { chartGeometry, type SpeedPoint } from '../../lib/speed-test';

const WIDTH = 400;
const HEIGHT = 200;
const PADDING = 24;

/** Decode speed (tokens per second) against context size (tokens), one point per turn. */
export function SpeedChart({ points }: { points: SpeedPoint[] }) {
  const g = chartGeometry(points, WIDTH, HEIGHT, PADDING);
  const line = g.points.map((p) => `${p.x},${p.y}`).join(' ');
  return (
    <svg
      className="speed-chart"
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      role="img"
      aria-label="Decode speed against context size"
    >
      <line
        className="speed-chart__axis"
        x1={PADDING}
        y1={HEIGHT - PADDING}
        x2={WIDTH - PADDING}
        y2={HEIGHT - PADDING}
      />
      <line
        className="speed-chart__axis"
        x1={PADDING}
        y1={PADDING}
        x2={PADDING}
        y2={HEIGHT - PADDING}
      />
      {points.length > 1 ? (
        <polyline className="speed-chart__line" points={line} fill="none" />
      ) : null}
      {g.points.map((p, i) => (
        <circle key={i} className="speed-chart__dot" cx={p.x} cy={p.y} r={3.5} />
      ))}
      {points.length > 0 ? (
        <>
          <text
            className="speed-chart__label"
            x={PADDING}
            y={HEIGHT - 6}
          >{`${g.xMin.toLocaleString('en-GB')} tokens`}</text>
          <text
            className="speed-chart__label speed-chart__label--end"
            x={WIDTH - PADDING}
            y={HEIGHT - 6}
          >
            {`${g.xMax.toLocaleString('en-GB')} tokens`}
          </text>
          <text
            className="speed-chart__label"
            x={PADDING + 4}
            y={PADDING - 4}
          >{`${g.yMax.toFixed(1)} tokens/s`}</text>
          <text
            className="speed-chart__label"
            x={PADDING + 4}
            y={HEIGHT - PADDING - 4}
          >{`${g.yMin.toFixed(1)} tokens/s`}</text>
        </>
      ) : null}
    </svg>
  );
}
