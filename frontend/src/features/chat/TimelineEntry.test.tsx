import { describe, expect, it } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { TimelineEntry } from './TimelineEntry';
import type { TimelineItem } from '../../lib/thought-timeline';

const reasoning: TimelineItem = { kind: 'reasoning', key: '0', text: 'Let me think' };
const call: TimelineItem = {
  kind: 'call',
  key: '1:call',
  name: 'web_search',
  args: '{"q":"x"}',
  running: false,
};
const result: TimelineItem = {
  kind: 'result',
  key: '1:result',
  name: 'web_search',
  result: 'ten hits',
};

describe('TimelineEntry', () => {
  it('labels each kind', () => {
    render(
      <>
        <TimelineEntry item={reasoning} />
        <TimelineEntry item={call} />
        <TimelineEntry item={result} />
        <TimelineEntry item={{ kind: 'event', key: '2', text: 'Searching' }} />
      </>,
    );
    expect(screen.getByRole('button', { name: /Reasoning/ })).toBeTruthy();
    expect(screen.getByRole('button', { name: /Call: Web search/ })).toBeTruthy();
    expect(screen.getByRole('button', { name: /Result: Web search/ })).toBeTruthy();
    expect(screen.getByRole('separator', { name: 'Searching' })).toBeTruthy();
  });

  it('is collapsed until clicked, and a click toggles it', () => {
    const { container } = render(<TimelineEntry item={reasoning} />);
    const header = screen.getByRole('button', { name: /Reasoning/ });
    expect(header.getAttribute('aria-expanded')).toBe('false');
    expect(container.querySelector('.activity-content-wrapper')?.hasAttribute('inert')).toBe(true);
    fireEvent.click(header);
    expect(header.getAttribute('aria-expanded')).toBe('true');
    expect(container.querySelector('.activity-item.expanded')).toBeTruthy();
    expect(container.querySelector('.activity-content-wrapper')?.hasAttribute('inert')).toBe(false);
    fireEvent.click(header);
    expect(header.getAttribute('aria-expanded')).toBe('false');
  });

  it('shows pretty-printed arguments and the result text when opened', () => {
    render(
      <>
        <TimelineEntry item={call} defaultOpen />
        <TimelineEntry item={result} defaultOpen />
      </>,
    );
    expect(screen.getByRole('group', { name: 'Arguments' }).textContent).toBe('{\n  "q": "x"\n}');
    expect(screen.getByRole('group', { name: 'Result' }).textContent).toBe('ten hits');
  });

  it('marks a running call', () => {
    render(<TimelineEntry item={{ ...call, running: true }} />);
    expect(screen.getByText('Running')).toBeTruthy();
  });

  it('a group shows its nested entries when opened', () => {
    const group: TimelineItem = {
      kind: 'group',
      key: 'g0',
      label: 'Browsing agent',
      items: [reasoning, call],
    };
    render(<TimelineEntry item={group} defaultOpen />);
    expect(screen.getByRole('button', { name: /Browsing agent/ })).toBeTruthy();
    expect(screen.getByRole('button', { name: /Reasoning/ })).toBeTruthy();
    expect(screen.getByRole('button', { name: /Call: Web search/ })).toBeTruthy();
  });

  it('carries no bubble styling in a body', () => {
    const { container } = render(<TimelineEntry item={reasoning} defaultOpen />);
    expect(container.querySelector('.message-content, .raw-text-content')).toBeNull();
    expect(container.querySelector('.activity-body .timeline-reasoning')).toBeTruthy();
  });
});
