import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import type { CodeRun } from '../../api/filesystem';
import { RunCard } from './RunCard';

const run = (over: Partial<CodeRun> = {}): CodeRun => ({
  id: 'r1',
  chat_id: 'c1',
  language: 'python',
  code: 'print(1)',
  stdin: null,
  stdout: '1\n',
  stderr: null,
  exit_code: 0,
  execution_time_ms: 5,
  timed_out: 0,
  created_at: null,
  ...over,
});

describe('RunCard outcome', () => {
  it.each([
    [{}, 'Passed'],
    [{ exit_code: 2 }, 'Failed (exit 2)'],
    [{ exit_code: null }, 'Failed'],
    [{ timed_out: 1, exit_code: null }, 'Timed out'],
  ] as Array<[Partial<CodeRun>, string]>)('%j is labelled %s', (over, label) => {
    render(<RunCard run={run(over)} />);
    expect(screen.getByText(label)).toBeTruthy();
  });

  it('puts code, output and errors in separate named groups and omits empty ones', () => {
    const full = render(<RunCard run={run({ stderr: 'oops' })} />);
    expect(screen.getByRole('group', { name: 'Code' }).textContent).toBe('print(1)');
    expect(screen.getByRole('group', { name: 'Output' }).textContent).toBe('1\n');
    expect(screen.getByRole('group', { name: 'Errors' }).textContent).toBe('oops');
    full.unmount();
    render(<RunCard run={run({ stdout: null })} />);
    expect(screen.queryByRole('group', { name: 'Output' })).toBeNull();
    expect(screen.queryByRole('group', { name: 'Errors' })).toBeNull();
  });

  it('reads a time that already carries a zone', () => {
    const view = render(<RunCard run={run({ created_at: '2026-11-10T08:06:20Z' })} />);
    expect(view.container.querySelector('time')?.getAttribute('datetime')).toBe(
      '2026-11-10T08:06:20Z',
    );
    view.unmount();
    const offset = render(<RunCard run={run({ created_at: '2026-11-10T10:06:20+02:00' })} />);
    const time = offset.container.querySelector('time') as HTMLTimeElement;
    expect(time.getAttribute('datetime')).toBe('2026-11-10T10:06:20+02:00');
    expect(time.textContent).toBe(new Date('2026-11-10T10:06:20+02:00').toLocaleString());
  });

  it("shows the time in the reader's locale and keeps the raw value for machines; an unreadable value is shown as is", () => {
    const view = render(<RunCard run={run({ created_at: '2026-11-10 08:06:20' })} />);
    const time = view.container.querySelector('time') as HTMLTimeElement;
    expect(time.getAttribute('datetime')).toBe('2026-11-10T08:06:20Z');
    expect(time.textContent).not.toBe('2026-11-10 08:06:20');
    view.unmount();
    const odd = render(<RunCard run={run({ created_at: 'yesterday' })} />);
    expect(Array.from(odd.container.querySelectorAll('.code-run__meta')).at(-1)?.textContent).toBe(
      'yesterday',
    );
  });
});
