import { afterEach, describe, expect, it } from 'vitest';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { ThoughtBox } from './ThoughtBox';
import { useThoughtStore } from '../../state/thought-store';
import type { TimelineItem } from '../../lib/thought-timeline';

const items: TimelineItem[] = [
  { kind: 'reasoning', key: '0', text: 'Plan the search' },
  { kind: 'tool', key: '1', name: 'web_search', args: '{"q":"x"}', result: 'hits' },
  { kind: 'reasoning', key: '2', text: 'Write it up' },
];

function box(props: Partial<React.ComponentProps<typeof ThoughtBox>> = {}) {
  return <ThoughtBox turnKey="c1:1" items={items} active={false} status={null} {...props} />;
}

describe('ThoughtBox', () => {
  afterEach(() => useThoughtStore.setState({ expanded: {} }));

  it('says Thinking… with the status line while active, and Thought process once it has ended', () => {
    const { rerender } = render(box({ active: true, status: 'Searching the web' }));
    expect(screen.getByText(/Thinking…/)).toBeTruthy();
    expect(screen.getByText('Searching the web')).toBeTruthy();
    rerender(box({ active: false, status: 'Searching the web' }));
    expect(screen.getByText('Thought process')).toBeTruthy();
    expect(screen.queryByText('Searching the web')).toBeNull();
  });

  it('has no avatar, and lists the entries in order when expanded', () => {
    const { container } = render(box());
    expect(container.querySelector('.avatar, .assistant-avatar-column')).toBeNull();
    expect(screen.queryByText('Plan the search')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: /Thought process/ }));
    const all = container.querySelector('.activity-feed')?.textContent ?? '';
    const order = ['Plan the search', 'Web search', 'Write it up'].map((l) => all.indexOf(l));
    expect(order.every((i) => i >= 0)).toBe(true);
    expect([...order].sort((a, b) => a - b)).toEqual(order);
  });

  it('follows the store: an expanded key stays expanded on a re-rendered box', () => {
    act(() => useThoughtStore.getState().toggle('c1:1'));
    const { container, unmount } = render(box());
    expect(container.querySelector('.thought-container.expanded')).toBeTruthy();
    unmount();
    const again = render(box({ active: false }));
    expect(again.container.querySelector('.thought-container.expanded')).toBeTruthy();
    expect(
      screen.getByRole('button', { name: /Thought process/ }).getAttribute('aria-expanded'),
    ).toBe('true');
  });

  it('"Open bigger" in the open box opens a window with every entry open, and Escape closes it', () => {
    render(box());
    expect(screen.queryByRole('button', { name: 'Open bigger' })).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: /Thought process/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Open bigger' }));
    const dialog = screen.getByRole('dialog');
    expect(dialog.textContent).toContain('Plan the search');
    expect(dialog.textContent).toContain('hits');
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('the header is one button, and nothing is offered to open when there is nothing to show', () => {
    const { container } = render(box({ items: [], active: true }));
    expect(container.querySelectorAll('button button').length).toBe(0);
    expect(container.querySelectorAll('.thought-header button').length).toBe(1);
    fireEvent.click(screen.getByRole('button', { name: /Thinking/ }));
    expect(screen.queryByRole('button', { name: 'Open bigger' })).toBeNull();
  });
});
