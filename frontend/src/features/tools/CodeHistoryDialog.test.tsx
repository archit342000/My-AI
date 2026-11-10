import { afterEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import { renderWithProviders } from '../../test/render';
import { CodeHistoryDialog } from './CodeHistoryDialog';
import { codeExecApi, type CodeRun } from '../../api/filesystem';
import { ApiError } from '../../api/client';
import { useStreamStore } from '../../state/stream-store';

const run = (over: Partial<CodeRun> = {}): CodeRun => ({
  id: 'r1',
  chat_id: 'c1',
  language: 'python',
  code: 'print(1 + 1)',
  stdin: null,
  stdout: '2\n',
  stderr: null,
  exit_code: 0,
  execution_time_ms: 42,
  timed_out: 0,
  created_at: '2026-11-10 10:00:00',
  ...over,
});

describe('CodeHistoryDialog', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    useStreamStore.setState({
      chatId: null,
      live: null,
      pending: null,
      interrupted: null,
      controller: null,
    });
  });

  it('reads the chat that is open, not the one that is streaming', async () => {
    useStreamStore.setState({
      chatId: 'other',
      live: null,
      pending: null,
      interrupted: null,
      controller: null,
    });
    const history = vi.spyOn(codeExecApi, 'history').mockResolvedValue([]);
    renderWithProviders(<CodeHistoryDialog open onClose={() => undefined} />, {
      route: '/chat/c1',
      path: '/chat/:chatId',
    });
    await waitFor(() => expect(history).toHaveBeenCalledWith('c1'));
    expect(history).not.toHaveBeenCalledWith('other');
  });

  it('shows each run as a card with its code and output in separate blocks', async () => {
    vi.spyOn(codeExecApi, 'history').mockResolvedValue([
      run(),
      run({ id: 'r2', code: 'raise SystemExit(1)', stdout: null, stderr: 'boom', exit_code: 1 }),
    ]);
    renderWithProviders(<CodeHistoryDialog open onClose={() => undefined} />, {
      route: '/chat/c1',
      path: '/chat/:chatId',
    });
    expect(await screen.findByText('print(1 + 1)')).toBeTruthy();
    const cards = document.querySelectorAll('.code-run');
    expect(cards).toHaveLength(2);
    expect(cards[0]?.querySelector('[role="group"][aria-label="Code"] pre')?.textContent).toBe(
      'print(1 + 1)',
    );
    expect(cards[0]?.querySelector('[role="group"][aria-label="Output"] pre')?.textContent).toBe(
      '2\n',
    );
    expect(cards[0]?.textContent).toContain('Passed');
    expect(cards[1]?.querySelector('[role="group"][aria-label="Errors"] pre')?.textContent).toBe(
      'boom',
    );
    expect(cards[1]?.textContent).toContain('Failed (exit 1)');
  });

  it('marks a run that timed out', async () => {
    vi.spyOn(codeExecApi, 'history').mockResolvedValue([run({ timed_out: 1, exit_code: null })]);
    renderWithProviders(<CodeHistoryDialog open onClose={() => undefined} />, {
      route: '/chat/c1',
      path: '/chat/:chatId',
    });
    expect(await screen.findByText('Timed out')).toBeTruthy();
  });

  it('shows Loading… while the runs load', () => {
    vi.spyOn(codeExecApi, 'history').mockReturnValue(new Promise(() => undefined));
    renderWithProviders(<CodeHistoryDialog open onClose={() => undefined} />, {
      route: '/chat/c1',
      path: '/chat/:chatId',
    });
    expect(screen.getByText('Loading…')).toBeTruthy();
  });

  it('labels a run with no exit code and no timeout as Failed, and copes with missing time fields', async () => {
    vi.spyOn(codeExecApi, 'history').mockResolvedValue([
      run({
        exit_code: null,
        timed_out: null,
        execution_time_ms: null,
        created_at: null,
        stdout: null,
      }),
    ]);
    renderWithProviders(<CodeHistoryDialog open onClose={() => undefined} />, {
      route: '/chat/c1',
      path: '/chat/:chatId',
    });
    expect(await screen.findByText('Failed')).toBeTruthy();
    expect(document.querySelector('.code-run__meta')).toBeNull();
  });

  it('shows an error state when the runs cannot be loaded', async () => {
    vi.spyOn(codeExecApi, 'history').mockRejectedValue(new ApiError(403, {}, 'not your chat'));
    renderWithProviders(<CodeHistoryDialog open onClose={() => undefined} />, {
      route: '/chat/c1',
      path: '/chat/:chatId',
    });
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('not your chat'));
  });

  it('says so when there are no runs, and when no chat is open', async () => {
    const history = vi.spyOn(codeExecApi, 'history').mockResolvedValue([]);
    const first = renderWithProviders(<CodeHistoryDialog open onClose={() => undefined} />, {
      route: '/chat/c1',
      path: '/chat/:chatId',
    });
    expect(await screen.findByText('No runs yet.')).toBeTruthy();
    first.unmount();
    history.mockClear();
    renderWithProviders(<CodeHistoryDialog open onClose={() => undefined} />);
    expect(screen.getByText('Open a chat to see its runs.')).toBeTruthy();
    expect(history).not.toHaveBeenCalled();
  });
});
