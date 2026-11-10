/**
 * State of a model speed test, built from the events `/api/models/test-speed` streams.
 * Formulas follow the legacy telemetry panel: time to first token is the prompt time in ms, prefill and
 * decode speeds are tokens per second, and the three figures shown are averages over the turns so far.
 */

export interface SpeedPoint {
  contextTokens: number;
  decodeTps: number;
}

export interface SpeedTestState {
  status: string;
  turns: number;
  avgTtftMs: number;
  avgPrefillTps: number;
  avgDecodeTps: number;
  contextTokens: number;
  points: SpeedPoint[];
  /** Messages the server sent as `error` events; the run goes on after them. */
  warnings: string[];
  completed: boolean;
  ttftSum: number;
  prefillSum: number;
  decodeSum: number;
  /** Per turn: whether the timings were counted, whether the first token arrived, and the not yet plotted figures. */
  timingsSeen: boolean;
  generating: boolean;
  pendingTokens: number;
  pendingDecodeTps: number | null;
}

export function emptySpeedTest(): SpeedTestState {
  return {
    status: '',
    turns: 0,
    avgTtftMs: 0,
    avgPrefillTps: 0,
    avgDecodeTps: 0,
    contextTokens: 0,
    points: [],
    warnings: [],
    completed: false,
    ttftSum: 0,
    prefillSum: 0,
    decodeSum: 0,
    timingsSeen: false,
    generating: false,
    pendingTokens: 0,
    pendingDecodeTps: null,
  };
}

interface SpeedEvent {
  error?: unknown;
  test_status?: unknown;
  choices?: Array<{ delta?: Record<string, unknown> }>;
  timings?: { prompt_ms?: number; prompt_n?: number; predicted_ms?: number; predicted_n?: number };
  usage?: { total_tokens?: number };
}

/** Reads a number from the server; anything that is not a finite number counts as 0. */
const num = (value: unknown): number =>
  typeof value === 'number' && Number.isFinite(value) ? value : 0;

const perSecond = (tokens: number, ms: number) => (ms > 0 ? tokens / (ms / 1000) : 0);

/** Folds one streamed event into the state. Unknown shapes are ignored. */
export function applySpeedEvent(state: SpeedTestState, raw: unknown): SpeedTestState {
  if (!raw || typeof raw !== 'object') return state;
  const event = raw as SpeedEvent;
  let next = state;

  if (typeof event.error === 'string') {
    next = { ...next, warnings: [...next.warnings, event.error] };
  }

  if (typeof event.test_status === 'string') {
    const status = event.test_status;
    next = { ...next, status };
    if (status.startsWith('Starting Turn')) {
      next = {
        ...next,
        timingsSeen: false,
        generating: false,
        pendingTokens: 0,
        pendingDecodeTps: null,
      };
    }
    if (status.startsWith('Completed')) next = { ...next, completed: true };
  }

  const delta = event.choices?.[0]?.delta;
  if (delta && 'content' in delta && !next.generating) {
    next = { ...next, generating: true, status: 'Streaming Generation...' };
  }

  if (event.timings && !next.timingsSeen) {
    const promptMs = num(event.timings.prompt_ms);
    const predictedMs = num(event.timings.predicted_ms);
    const promptN = num(event.timings.prompt_n);
    const predictedN = num(event.timings.predicted_n);
    const turns = next.turns + 1;
    const decodeTps = perSecond(predictedN, predictedMs);
    const ttftSum = next.ttftSum + promptMs;
    const prefillSum = next.prefillSum + perSecond(promptN, promptMs);
    const decodeSum = next.decodeSum + decodeTps;
    const fallbackTokens =
      !event.usage?.total_tokens && promptN + predictedN > 0 ? promptN + predictedN : 0;
    next = {
      ...next,
      timingsSeen: true,
      turns,
      ttftSum,
      prefillSum,
      decodeSum,
      avgTtftMs: ttftSum / turns,
      avgPrefillTps: prefillSum / turns,
      avgDecodeTps: decodeSum / turns,
      pendingDecodeTps: decodeTps,
      ...(fallbackTokens > 0
        ? { pendingTokens: fallbackTokens, contextTokens: fallbackTokens }
        : {}),
    };
  }

  const total = num(event.usage?.total_tokens);
  if (total) next = { ...next, pendingTokens: total, contextTokens: total };

  // A turn is plotted once both its context size and its decode speed are known.
  if (next.pendingTokens > 0 && next.pendingDecodeTps !== null) {
    next = {
      ...next,
      points: [
        ...next.points,
        { contextTokens: next.pendingTokens, decodeTps: next.pendingDecodeTps },
      ],
      pendingTokens: 0,
      pendingDecodeTps: null,
    };
  }
  return next;
}

/** Called when the stream ends: a run that never reported completion has failed. */
export function finishSpeedTest(state: SpeedTestState): {
  state: SpeedTestState;
  error: string | null;
} {
  if (state.completed) return { state, error: null };
  const error =
    state.warnings[state.warnings.length - 1] ?? 'The speed test ended before it completed.';
  return { state: { ...state, status: 'Failed' }, error };
}

export interface ChartGeometry {
  points: Array<{ x: number; y: number }>;
  xMin: number;
  xMax: number;
  yMin: number;
  yMax: number;
}

/** Maps points to a plot area: the lowest context to the left edge, the highest decode speed to the top. */
export function chartGeometry(
  points: SpeedPoint[],
  width: number,
  height: number,
  padding = 24,
): ChartGeometry {
  const xs = points.map((p) => p.contextTokens);
  const ys = points.map((p) => p.decodeTps);
  const xMin = xs.length ? Math.min(...xs) : 0;
  const xMax = xs.length ? Math.max(...xs) : 0;
  const yMin = ys.length ? Math.min(...ys) : 0;
  const yMax = ys.length ? Math.max(...ys) : 0;
  const plotW = width - 2 * padding;
  const plotH = height - 2 * padding;
  const place = (value: number, min: number, max: number, size: number) =>
    max > min ? ((value - min) / (max - min)) * size : size / 2;
  return {
    xMin,
    xMax,
    yMin,
    yMax,
    points: points.map((p) => ({
      x: padding + place(p.contextTokens, xMin, xMax, plotW),
      y: height - padding - place(p.decodeTps, yMin, yMax, plotH),
    })),
  };
}
