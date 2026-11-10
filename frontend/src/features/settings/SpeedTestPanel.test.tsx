import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import { renderWithProviders } from '../../test/render';
import { abortableSseResponse, sseResponse, sseText } from '../../test/fixtures/sse';
import { SpeedTestPanel } from './SpeedTestPanel';

const models = [{ id: 'A', status: { value: 'loaded' } }];
const turn = [
  { test_status: 'Starting Turn 1 (Current Context: 0/8000)' },
  { choices: [{ delta: { content: 'hi' } }] },
  {
    timings: { prompt_ms: 500, prompt_n: 1000, predicted_ms: 2000, predicted_n: 100 },
    usage: { total_tokens: 1100 },
  },
];

function chooseModel() {
  fireEvent.click(screen.getByRole('combobox', { name: 'Speed test target' }));
  fireEvent.click(screen.getByRole('option', { name: /^A\b/ }));
}

async function startRun() {
  chooseModel();
  fireEvent.click(screen.getByRole('button', { name: 'Run speed test' }));
  fireEvent.click(await screen.findByRole('button', { name: 'Run' }));
}

describe('SpeedTestPanel', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('asks for confirmation, then runs with the chosen model and context and shows the figures', async () => {
    const fetchMock = vi.fn(async () =>
      sseResponse(sseText([...turn, { test_status: 'Completed: done' }])),
    );
    vi.stubGlobal('fetch', fetchMock);
    renderWithProviders(<SpeedTestPanel models={models} />);
    chooseModel();
    // The number box commits on blur.
    const box = screen.getByRole('spinbutton', { name: 'Target context (tokens) value' });
    fireEvent.change(box, { target: { value: '8000' } });
    fireEvent.blur(box);
    fireEvent.click(screen.getByRole('button', { name: 'Run speed test' }));
    expect(fetchMock).not.toHaveBeenCalled();
    expect(screen.getByText(/unloads every loaded model/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Run' }));
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Completed: done'));
    const init = (fetchMock.mock.calls[0] as unknown as [string, RequestInit])[1];
    expect(JSON.parse(String(init.body))).toEqual({ model: 'A', target_context_threshold: 8000 });
    const figures = document.querySelector('.speed-test__figures') as HTMLElement;
    expect(within(figures).getByText('1,100')).toBeTruthy();
    expect(within(figures).getByText('500 ms')).toBeTruthy();
    expect(within(figures).getByText('2000.00 tok/s')).toBeTruthy();
    expect(within(figures).getByText('50.00 tok/s')).toBeTruthy();
    expect(document.querySelectorAll('.speed-chart__dot')).toHaveLength(1);
  });

  it('cancelling the confirmation starts nothing', () => {
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    renderWithProviders(<SpeedTestPanel models={models} />);
    chooseModel();
    fireEvent.click(screen.getByRole('button', { name: 'Run speed test' }));
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('shows Stop only while running and stops the run', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (_url: string, init: RequestInit) =>
        abortableSseResponse(turn, init.signal as AbortSignal),
      ),
    );
    renderWithProviders(<SpeedTestPanel models={models} />);
    expect(screen.queryByRole('button', { name: 'Stop' })).toBeNull();
    await startRun();
    fireEvent.click(await screen.findByRole('button', { name: 'Stop' }));
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Stopped'));
    expect(screen.queryByRole('button', { name: 'Stop' })).toBeNull();
    expect(
      (screen.getByRole('button', { name: 'Run speed test' }) as HTMLButtonElement).disabled,
    ).toBe(false);
  });

  it('a failed run shows the server error and Run is usable again', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(
        async () => new Response(JSON.stringify({ error: 'Model not found' }), { status: 404 }),
      ),
    );
    renderWithProviders(<SpeedTestPanel models={models} />);
    await startRun();
    expect(await screen.findByText('Model not found')).toBeTruthy();
    expect(
      (screen.getByRole('button', { name: 'Run speed test' }) as HTMLButtonElement).disabled,
    ).toBe(false);
  });

  it('lists stream warnings of a run that carried on', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        sseResponse(
          sseText([
            { error: 'Failed to fully unload. Proceeding anyway...' },
            ...turn,
            { test_status: 'Completed' },
          ]),
        ),
      ),
    );
    renderWithProviders(<SpeedTestPanel models={models} />);
    await startRun();
    expect(await screen.findByText('Failed to fully unload. Proceeding anyway...')).toBeTruthy();
  });
});
