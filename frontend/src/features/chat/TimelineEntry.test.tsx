import { describe, expect, it } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { TimelineEntry } from './TimelineEntry';
import type { TimelineItem } from '../../lib/thought-timeline';

const reasoning: TimelineItem = { kind: 'reasoning', key: '0', text: 'Let me think' };
const tool: TimelineItem = {
  kind: 'tool',
  key: '1',
  name: 'web_search',
  args: '{"q":"flaky login test"}',
  result: 'ten hits',
};

describe('TimelineEntry', () => {
  it('a thought is plain text on the line, not something to open', () => {
    const { container } = render(<TimelineEntry item={reasoning} />);
    expect(screen.getByText('Let me think')).toBeTruthy();
    expect(screen.queryByRole('button')).toBeNull();
    expect(container.querySelector('.timeline-reasoning')).toBeTruthy();
    expect(container.querySelector('.message-content, .raw-text-content')).toBeNull();
  });

  it('a tool call is one row: a light, its plain name and what it was asked', () => {
    const { container } = render(<TimelineEntry item={tool} />);
    const row = screen.getByRole('button', { name: /Web search/ });
    expect(row.textContent).toContain('flaky login test');
    expect(row.textContent).not.toMatch(/Call:|Result:/);
    expect(container.querySelector('.led.ok')).toBeTruthy();
    expect(screen.queryByText('Running')).toBeNull();
  });

  it('an activity line is a divider', () => {
    render(<TimelineEntry item={{ kind: 'event', key: '2', text: 'Searching' }} />);
    expect(screen.getByRole('separator', { name: 'Searching' })).toBeTruthy();
  });

  it('is folded until clicked, and a click toggles it', () => {
    const { container } = render(<TimelineEntry item={tool} />);
    const header = screen.getByRole('button', { name: /Web search/ });
    expect(header.getAttribute('aria-expanded')).toBe('false');
    expect(container.querySelector('.activity-content-wrapper')?.hasAttribute('inert')).toBe(true);
    fireEvent.click(header);
    expect(header.getAttribute('aria-expanded')).toBe('true');
    expect(container.querySelector('.activity-item.expanded')).toBeTruthy();
    expect(container.querySelector('.activity-content-wrapper')?.hasAttribute('inert')).toBe(false);
    fireEvent.click(header);
    expect(header.getAttribute('aria-expanded')).toBe('false');
  });

  it('opened, it shows what was asked (pretty-printed) and what came back', () => {
    render(<TimelineEntry item={tool} defaultOpen />);
    expect(screen.getByRole('group', { name: 'Asked' }).textContent).toBe(
      '{\n  "q": "flaky login test"\n}',
    );
    expect(screen.getByRole('group', { name: 'Answer' }).textContent).toBe('ten hits');
  });

  it('a call still running says so, pulses, and has no answer yet', () => {
    const { container } = render(<TimelineEntry item={{ ...tool, result: null }} defaultOpen />);
    expect(screen.getByText('Running')).toBeTruthy();
    expect(container.querySelector('.led.busy')).toBeTruthy();
    expect(screen.queryByRole('group', { name: 'Answer' })).toBeNull();
  });

  it('a call that failed says so in words as well as colour', () => {
    const { container } = render(<TimelineEntry item={{ ...tool, result: 'Error: no network' }} />);
    expect(screen.getByText('Failed')).toBeTruthy();
    expect(container.querySelector('.led.bad')).toBeTruthy();
  });

  it("a helper's steps are a box holding their own line of entries", () => {
    const group: TimelineItem = {
      kind: 'group',
      key: 'g0',
      label: 'Browsing agent',
      items: [reasoning, tool],
    };
    render(<TimelineEntry item={group} defaultOpen />);
    expect(screen.getByRole('button', { name: /Browsing agent/ })).toBeTruthy();
    expect(screen.getByText('Let me think')).toBeTruthy();
    expect(screen.getByRole('button', { name: /Web search/ })).toBeTruthy();
  });
});
