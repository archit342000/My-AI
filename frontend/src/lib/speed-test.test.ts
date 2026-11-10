import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { readSse } from '../api/sse';
import {
  applySpeedEvent,
  chartGeometry,
  emptySpeedTest,
  finishSpeedTest,
  type SpeedTestState,
} from './speed-test';

function load(name: string): ReadableStream<Uint8Array> {
  const bytes = new TextEncoder().encode(
    readFileSync(resolve(__dirname, `../test/fixtures/stream/${name}.sse`), 'utf8'),
  );
  return new ReadableStream({
    start(c) {
      for (let i = 0; i < bytes.length; i += 23) c.enqueue(bytes.slice(i, i + 23));
      c.close();
    },
  });
}

async function run(name: string): Promise<SpeedTestState> {
  let state = emptySpeedTest();
  for await (const event of readSse(load(name))) state = applySpeedEvent(state, event);
  return state;
}

describe('speed test reducer', () => {
  it('averages two turns of the recorded stream', async () => {
    const state = await run('speed-test');
    expect(state.turns).toBe(2);
    // Time to first token is the prompt time in ms.
    expect(state.avgTtftMs).toBe(750);
    // Turn 1: 1000 / 0.5 s = 2000, turn 2: 3000 / 1 s = 3000.
    expect(state.avgPrefillTps).toBe(2500);
    // Turn 1: 100 / 2 s = 50, turn 2: 100 / 4 s = 25.
    expect(state.avgDecodeTps).toBe(37.5);
    expect(state.contextTokens).toBe(4200);
    expect(state.points).toEqual([
      { contextTokens: 1100, decodeTps: 50 },
      { contextTokens: 4200, decodeTps: 25 },
    ]);
    expect(state.status).toBe('Completed: reached the target context');
    expect(finishSpeedTest(state).error).toBeNull();
  });

  it('takes the context size from the timings when there is no usage', () => {
    const state = applySpeedEvent(emptySpeedTest(), {
      timings: { prompt_ms: 100, prompt_n: 50, predicted_ms: 100, predicted_n: 10 },
    });
    expect(state.contextTokens).toBe(60);
    expect(state.points).toEqual([{ contextTokens: 60, decodeTps: 100 }]);
  });

  it('plots a turn once usage arrives after its timings', () => {
    let state = applySpeedEvent(emptySpeedTest(), {
      timings: { prompt_ms: 100, prompt_n: 0, predicted_ms: 1000, predicted_n: 0 },
    });
    expect(state.points).toEqual([]);
    state = applySpeedEvent(state, { usage: { total_tokens: 500 } });
    expect(state.points).toEqual([{ contextTokens: 500, decodeTps: 0 }]);
  });

  it('counts the timings of a turn once', () => {
    const timings = { prompt_ms: 100, prompt_n: 10, predicted_ms: 100, predicted_n: 10 };
    let state = applySpeedEvent(emptySpeedTest(), { timings });
    state = applySpeedEvent(state, { timings });
    expect(state.turns).toBe(1);
  });

  it('gives zero speeds for a zero or missing time', () => {
    const state = applySpeedEvent(emptySpeedTest(), { timings: { prompt_n: 10, predicted_n: 10 } });
    expect(state.avgPrefillTps).toBe(0);
    expect(state.avgDecodeTps).toBe(0);
  });

  it('shows the first generated token as streaming', () => {
    const state = applySpeedEvent(emptySpeedTest(), { choices: [{ delta: { content: 'hi' } }] });
    expect(state.status).toBe('Streaming Generation...');
  });

  it('keeps an error event as a warning and carries on', () => {
    let state = applySpeedEvent(emptySpeedTest(), {
      error: 'Failed to fully unload. Proceeding anyway...',
    });
    state = applySpeedEvent(state, { test_status: 'Completed' });
    expect(state.warnings).toEqual(['Failed to fully unload. Proceeding anyway...']);
    expect(finishSpeedTest(state).error).toBeNull();
  });

  it('fails a stream that ends without completing, with the last warning', () => {
    let state = applySpeedEvent(emptySpeedTest(), { test_status: 'Loading model...' });
    state = applySpeedEvent(state, { error: 'model failed to load' });
    const result = finishSpeedTest(state);
    expect(result.error).toBe('model failed to load');
    expect(result.state.status).toBe('Failed');
  });

  it('fails a stream that was cut off while generating', () => {
    const state = applySpeedEvent(emptySpeedTest(), { choices: [{ delta: { content: 'x' } }] });
    expect(finishSpeedTest(state)).toMatchObject({
      error: 'The speed test ended before it completed.',
      state: { status: 'Failed' },
    });
  });

  it('treats non-numeric figures as zero instead of NaN', () => {
    const state = applySpeedEvent(emptySpeedTest(), {
      timings: { prompt_ms: 'x', prompt_n: null, predicted_ms: 100, predicted_n: 10 },
      usage: { total_tokens: 'many' },
    });
    expect(state.avgTtftMs).toBe(0);
    expect(state.avgPrefillTps).toBe(0);
    expect(state.avgDecodeTps).toBe(100);
  });

  it('ignores events of an unknown shape', () => {
    const state = emptySpeedTest();
    expect(applySpeedEvent(state, null)).toBe(state);
    expect(applySpeedEvent(state, 'text')).toBe(state);
  });
});

describe('chartGeometry', () => {
  it('maps the extreme points to the corners of the plot', () => {
    const g = chartGeometry(
      [
        { contextTokens: 1000, decodeTps: 10 },
        { contextTokens: 5000, decodeTps: 50 },
      ],
      200,
      100,
      10,
    );
    expect(g.points[0]).toEqual({ x: 10, y: 90 });
    expect(g.points[1]).toEqual({ x: 190, y: 10 });
    expect([g.xMin, g.xMax, g.yMin, g.yMax]).toEqual([1000, 5000, 10, 50]);
  });

  it('centres a single point and handles no points', () => {
    expect(chartGeometry([{ contextTokens: 5, decodeTps: 5 }], 200, 100, 10).points[0]).toEqual({
      x: 100,
      y: 50,
    });
    expect(chartGeometry([], 200, 100).points).toEqual([]);
  });
});
